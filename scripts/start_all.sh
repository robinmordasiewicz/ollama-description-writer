#!/bin/bash
# Start Complete Toolchain: MCP Bridge + vLLM
# Usage: ./scripts/start_all.sh [start|stop|restart|status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

header() {
    echo -e "${CYAN}=== $1 ===${NC}"
}

start_all() {
    header "Starting Complete Toolchain"
    echo ""

    # Step 1: Start MCP Bridge
    log_info "Step 1/2: Starting MCP bridge..."
    "${SCRIPT_DIR}/mcp_bridge.sh" start

    # Wait for bridge to be ready
    sleep 3

    # Step 2: Stop existing vLLM and restart with new tool server
    log_info "Step 2/2: Starting vLLM server..."
    "${SCRIPT_DIR}/vllm_server.sh" restart

    echo ""
    header "Toolchain Ready"
    echo ""
    echo "Services:"
    echo "  - MCP Bridge:  http://localhost:8080/sse (f5xc-api-mcp)"
    echo "  - vLLM Server: http://localhost:8000/v1"
    echo ""
    echo "Tools available: 1500+ F5 Distributed Cloud API tools"
    echo ""
    echo "Test with:"
    echo "  curl -X POST http://localhost:8000/v1/chat/completions \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"model\": \"Qwen/Qwen2.5-7B-Instruct\", \"messages\": [{\"role\": \"user\", \"content\": \"List F5XC API tools\"}]}'"
}

stop_all() {
    header "Stopping All Services"
    echo ""

    log_info "Stopping vLLM server..."
    "${SCRIPT_DIR}/vllm_server.sh" stop || true

    log_info "Stopping MCP bridge..."
    "${SCRIPT_DIR}/mcp_bridge.sh" stop || true

    echo ""
    log_info "All services stopped"
}

restart_all() {
    stop_all
    sleep 3
    start_all
}

show_status() {
    header "Toolchain Status"
    echo ""

    echo -e "${CYAN}MCP Bridge:${NC}"
    "${SCRIPT_DIR}/mcp_bridge.sh" status
    echo ""

    echo -e "${CYAN}vLLM Server:${NC}"
    "${SCRIPT_DIR}/vllm_server.sh" status
}

show_help() {
    echo "Complete Toolchain Management"
    echo ""
    echo "Manages MCP Bridge (f5xc-api-mcp) + vLLM Server"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start    Start both MCP bridge and vLLM server"
    echo "  stop     Stop both services"
    echo "  restart  Restart both services"
    echo "  status   Show status of all services"
    echo "  help     Show this help message"
    echo ""
    echo "Individual service scripts:"
    echo "  ./scripts/mcp_bridge.sh   - MCP bridge only"
    echo "  ./scripts/vllm_server.sh  - vLLM server only"
}

# Main command handler
case "${1:-help}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        show_status
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
