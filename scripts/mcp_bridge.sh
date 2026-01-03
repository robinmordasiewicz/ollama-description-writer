#!/bin/bash
# MCP Bridge for f5xc-api-mcp → vLLM integration
# Bridges stdio-based MCP server to HTTP SSE for vLLM's --tool-server
#
# Usage: ./scripts/mcp_bridge.sh [start|stop|restart|status|logs|help]

set -e

# Configuration
PORT=8080
LOG_FILE="/tmp/mcp_bridge.log"
PID_FILE="/tmp/mcp_bridge.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

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
    pgrep -f "mcp-proxy.*f5xc-api-mcp" 2>/dev/null || true
}

wait_for_bridge() {
    local max_attempts=30
    local attempt=0
    log_info "Waiting for MCP bridge to be ready..."

    while [ $attempt -lt $max_attempts ]; do
        # Check if port is listening
        if ss -tlnp 2>/dev/null | grep -q ":${PORT}"; then
            log_info "MCP bridge is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 1
    done

    echo ""
    log_error "MCP bridge failed to start within ${max_attempts} seconds"
    return 1
}

start_bridge() {
    local pid=$(get_pid)

    if [ -n "$pid" ]; then
        log_warn "MCP bridge is already running (PID: $pid)"
        return 0
    fi

    # Check for F5XC credentials
    if [ -z "$F5XC_API_URL" ] && [ ! -f ~/.f5xc/credentials.json ]; then
        log_warn "No F5XC credentials found. Running in documentation mode."
        log_info "To enable execution mode, run: npx @robinmordasiewicz/f5xc-api-mcp --setup"
    fi

    log_info "Starting MCP bridge for f5xc-api-mcp..."
    log_info "Port: ${PORT}"
    log_info "Log file: ${LOG_FILE}"

    # Activate virtual environment if it exists
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "${SCRIPT_DIR}/../venv/bin/activate" ]; then
        source "${SCRIPT_DIR}/../venv/bin/activate"
    fi

    # Use Node.js 24+ (required by f5xc-api-mcp)
    if [ -f ~/.nvm/nvm.sh ]; then
        source ~/.nvm/nvm.sh
        nvm use 24 > /dev/null 2>&1 || log_warn "Node.js 24 not available"
    fi

    # f5xc-api-mcp repo location (with synced specs)
    F5XC_MCP_DIR="${F5XC_MCP_DIR:-/home/robin/GIT/f5xc-api-mcp}"

    if [ ! -d "${F5XC_MCP_DIR}/specs" ]; then
        log_error "f5xc-api-mcp not found at ${F5XC_MCP_DIR}"
        log_info "Clone and setup: git clone https://github.com/robinmordasiewicz/f5xc-api-mcp.git"
        log_info "Then run: cd f5xc-api-mcp && npm install && npm run sync-specs"
        return 1
    fi

    # Build mcp-proxy command with optional credentials
    if [ -n "$F5XC_API_URL" ] && [ -n "$F5XC_API_TOKEN" ]; then
        log_info "F5XC credentials detected - enabling execution mode"
        log_info "Tenant: $F5XC_API_URL"
        # Use --pass-environment to pass F5XC_* vars to the spawned process
        nohup env F5XC_API_URL="$F5XC_API_URL" F5XC_API_TOKEN="$F5XC_API_TOKEN" \
            mcp-proxy --port ${PORT} --pass-environment -- \
            node ${F5XC_MCP_DIR}/dist/index.js > "${LOG_FILE}" 2>&1 &
    else
        # Start without credentials (documentation mode)
        nohup mcp-proxy --port ${PORT} -- \
            node ${F5XC_MCP_DIR}/dist/index.js > "${LOG_FILE}" 2>&1 &
    fi

    local new_pid=$!
    echo $new_pid > "${PID_FILE}"

    log_info "Started MCP bridge with PID: $new_pid"

    # Wait for bridge to be ready
    wait_for_bridge
}

stop_bridge() {
    local pid=$(get_pid)

    if [ -z "$pid" ]; then
        log_warn "MCP bridge is not running"
        return 0
    fi

    log_info "Stopping MCP bridge (PID: $pid)..."
    kill $pid 2>/dev/null || true

    # Wait for process to terminate
    local attempts=0
    while [ $attempts -lt 10 ]; do
        if [ -z "$(get_pid)" ]; then
            log_info "MCP bridge stopped successfully"
            rm -f "${PID_FILE}"
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done

    # Force kill if still running
    log_warn "Force killing MCP bridge..."
    kill -9 $pid 2>/dev/null || true
    rm -f "${PID_FILE}"
    log_info "MCP bridge stopped"
}

restart_bridge() {
    stop_bridge
    sleep 2
    start_bridge
}

show_status() {
    local pid=$(get_pid)

    echo -e "${CYAN}=== MCP Bridge Status ===${NC}"

    if [ -n "$pid" ]; then
        log_info "MCP bridge is running (PID: $pid)"

        # Check if port is listening
        if ss -tlnp 2>/dev/null | grep -q ":${PORT}"; then
            log_info "SSE endpoint: OK (http://localhost:${PORT}/sse)"
        else
            log_warn "SSE endpoint: NOT LISTENING"
        fi

        # Check actual auth mode from server logs
        local auth_mode=$(grep -o '"authMode":"[^"]*"' "${LOG_FILE}" 2>/dev/null | tail -1 | cut -d'"' -f4)
        local tenant=$(grep -o '"tenant":"[^"]*"' "${LOG_FILE}" 2>/dev/null | tail -1 | cut -d'"' -f4)

        if [ "$auth_mode" = "token" ]; then
            log_info "Mode: Execution (API calls enabled)"
            [ -n "$tenant" ] && log_info "Tenant: $tenant"
        elif [ "$auth_mode" = "none" ]; then
            log_warn "Mode: Documentation only (no credentials)"
        else
            log_warn "Mode: Unknown (check logs)"
        fi
    else
        log_warn "MCP bridge is not running"
    fi
}

show_logs() {
    if [ -f "${LOG_FILE}" ]; then
        tail -f "${LOG_FILE}"
    else
        log_error "Log file not found: ${LOG_FILE}"
    fi
}

show_help() {
    echo -e "${CYAN}MCP Bridge Management Script${NC}"
    echo ""
    echo "Bridges f5xc-api-mcp (stdio) to HTTP SSE for vLLM integration"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start    Start the MCP bridge"
    echo "  stop     Stop the MCP bridge"
    echo "  restart  Restart the MCP bridge"
    echo "  status   Show bridge status"
    echo "  logs     Tail the bridge logs"
    echo "  help     Show this help message"
    echo ""
    echo "Configuration:"
    echo "  Port:    ${PORT}"
    echo "  Log:     ${LOG_FILE}"
    echo "  SSE:     http://localhost:${PORT}/sse"
    echo ""
    echo "Environment Variables:"
    echo "  F5XC_API_URL    - F5 Distributed Cloud API URL"
    echo "  F5XC_API_TOKEN  - API authentication token"
    echo ""
    echo "Examples:"
    echo "  $0 start                    # Start bridge"
    echo "  $0 status                   # Check bridge status"
    echo "  export F5XC_API_URL=...     # Set credentials before start"
}

# Main command handler
case "${1:-help}" in
    start)
        start_bridge
        ;;
    stop)
        stop_bridge
        ;;
    restart)
        restart_bridge
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
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
