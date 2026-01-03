#!/bin/bash
# vLLM Server Management with MCP Support
# Usage: ./scripts/vllm_server.sh [start|stop|restart|status|logs|health]

set -e

# Configuration
MODEL="Qwen/Qwen2.5-7B-Instruct"
PORT=8000
TOOL_SERVER="${VLLM_TOOL_SERVER:-localhost:8080}"  # f5xc-api-mcp native HTTP/SSE
LOG_FILE="/tmp/vllm_mcp.log"
PID_FILE="/tmp/vllm_mcp.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

get_pid() {
    pgrep -f "vllm serve.*${MODEL}" 2>/dev/null || true
}

wait_for_server() {
    local max_attempts=60
    local attempt=0
    log_info "Waiting for server to be ready..."

    while [ $attempt -lt $max_attempts ]; do
        if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
            log_info "Server is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    echo ""
    log_error "Server failed to start within ${max_attempts} attempts"
    return 1
}

start_server() {
    local pid=$(get_pid)

    if [ -n "$pid" ]; then
        log_warn "vLLM server is already running (PID: $pid)"
        return 0
    fi

    log_info "Starting vLLM server with MCP support..."
    log_info "Model: ${MODEL}"
    log_info "Port: ${PORT}"
    log_info "Tool server: ${TOOL_SERVER}"
    log_info "Log file: ${LOG_FILE}"

    # Activate virtual environment if it exists
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "${SCRIPT_DIR}/../venv/bin/activate" ]; then
        source "${SCRIPT_DIR}/../venv/bin/activate"
    fi

    # Start vLLM with MCP support
    nohup vllm serve "${MODEL}" \
        --enable-auto-tool-choice \
        --tool-call-parser hermes \
        --tool-server "${TOOL_SERVER}" \
        --gpu-memory-utilization 0.95 \
        --max-model-len 4096 \
        --dtype half \
        --port ${PORT} \
        > "${LOG_FILE}" 2>&1 &

    local new_pid=$!
    echo $new_pid > "${PID_FILE}"

    log_info "Started vLLM with PID: $new_pid"

    # Wait for server to be ready
    wait_for_server
}

stop_server() {
    local pid=$(get_pid)

    if [ -z "$pid" ]; then
        log_warn "vLLM server is not running"
        return 0
    fi

    log_info "Stopping vLLM server (PID: $pid)..."
    kill $pid 2>/dev/null || true

    # Wait for process to terminate
    local attempts=0
    while [ $attempts -lt 10 ]; do
        if [ -z "$(get_pid)" ]; then
            log_info "Server stopped successfully"
            rm -f "${PID_FILE}"
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done

    # Force kill if still running
    log_warn "Force killing server..."
    kill -9 $pid 2>/dev/null || true
    rm -f "${PID_FILE}"
    log_info "Server stopped"
}

restart_server() {
    stop_server
    sleep 2
    start_server
}

show_status() {
    local pid=$(get_pid)

    if [ -n "$pid" ]; then
        log_info "vLLM server is running (PID: $pid)"

        # Check health endpoint
        if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
            log_info "Health check: OK"
        else
            log_warn "Health check: FAILED"
        fi

        # Show model info
        local models=$(curl -s "http://localhost:${PORT}/v1/models" 2>/dev/null)
        if [ -n "$models" ]; then
            log_info "Available models:"
            echo "$models" | python3 -c "import sys, json; data = json.load(sys.stdin); print('  - ' + '\n  - '.join([m['id'] for m in data.get('data', [])]))" 2>/dev/null || true
        fi
    else
        log_warn "vLLM server is not running"
    fi
}

show_logs() {
    if [ -f "${LOG_FILE}" ]; then
        tail -f "${LOG_FILE}"
    else
        log_error "Log file not found: ${LOG_FILE}"
    fi
}

health_check() {
    if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
        echo "healthy"
        return 0
    else
        echo "unhealthy"
        return 1
    fi
}

show_help() {
    echo "vLLM Server Management Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start    Start the vLLM server with MCP support"
    echo "  stop     Stop the vLLM server"
    echo "  restart  Restart the vLLM server"
    echo "  status   Show server status and health"
    echo "  logs     Tail the server logs"
    echo "  health   Quick health check (returns 'healthy' or 'unhealthy')"
    echo "  help     Show this help message"
    echo ""
    echo "Configuration:"
    echo "  Model:       ${MODEL}"
    echo "  Port:        ${PORT}"
    echo "  Tool server: ${TOOL_SERVER}"
    echo "  Log:         ${LOG_FILE}"
    echo ""
    echo "MCP Settings:"
    echo "  Tool parser: hermes"
    echo "  Tool server: ${TOOL_SERVER} (f5xc-api-mcp native HTTP/SSE)"
    echo ""
    echo "Environment Variables:"
    echo "  VLLM_TOOL_SERVER  Override tool server (default: localhost:8080)"
}

# Main command handler
case "${1:-help}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    health)
        health_check
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
