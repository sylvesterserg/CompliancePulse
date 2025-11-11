#!/usr/bin/env bash
# Configuration helper for CompliancePulse

BASE_DIR="$(dirname "$0")/.."
CONFIG_FILE="$BASE_DIR/config/.env"

usage() {
    echo "CompliancePulse Configuration Helper"
    echo ""
    echo "Usage: $(basename "$0") [command]"
    echo ""
    echo "Commands:"
    echo "  set-api-key <key>     Set OpenAI API key"
    echo "  show-token            Display current API token"
    echo "  show-config           Show all configuration"
    echo "  reset-token           Generate new API token"
    echo ""
}

set_api_key() {
    local key="$1"
    if [ -z "$key" ]; then
        echo "Usage: $(basename "$0") set-api-key <your-openai-key>"
        return 1
    fi
    
    sed -i '' "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$key/" "$CONFIG_FILE" 2>/dev/null || \
    sed -i "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$key/" "$CONFIG_FILE"
    echo "✓ OpenAI API key configured"
}

show_token() {
    echo "Current API Token:"
    grep "^API_TOKEN=" "$CONFIG_FILE" | cut -d= -f2
}

show_config() {
    echo "CompliancePulse Configuration:"
    cat "$CONFIG_FILE"
}

reset_token() {
    local new_token=$(openssl rand -hex 32)
    sed -i '' "s/API_TOKEN=.*/API_TOKEN=$new_token/" "$CONFIG_FILE" 2>/dev/null || \
    sed -i "s/API_TOKEN=.*/API_TOKEN=$new_token/" "$CONFIG_FILE"
    echo "✓ New API token generated:"
    echo "$new_token"
}

if [ $# -eq 0 ]; then
    usage
    exit 0
fi

case "$1" in
    set-api-key)
        set_api_key "$2"
        ;;
    show-token)
        show_token
        ;;
    show-config)
        show_config
        ;;
    reset-token)
        reset_token
        ;;
    *)
        echo "Unknown command: $1"
        usage
        exit 1
        ;;
esac
