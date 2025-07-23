#!/usr/bin/env bash
# Hover dialog for termtap using tmux display-popup

set -euo pipefail

# Default values
TITLE="${TERMTAP_TITLE:-Command Execution}"
MODE="${TERMTAP_MODE:-before}"
SESSION="${TERMTAP_SESSION:-unknown}"
COMMAND="${TERMTAP_COMMAND:-}"
OUTPUT="${TERMTAP_OUTPUT:-}"
PATTERN="${TERMTAP_PATTERN:-}"
TEMP_DIR="${TERMTAP_TEMP_DIR:-/tmp/termtap}"

# Result files
RESULT_FILE="$TEMP_DIR/hover-result"
MESSAGE_FILE="$TEMP_DIR/hover-message"

# Clean up old result files
rm -f "$RESULT_FILE" "$MESSAGE_FILE"

# Create content based on mode
create_content() {
    case "$MODE" in
        before)
            cat << EOF
Execute Command?

Command: $COMMAND
Session: $SESSION
Directory: $(pwd)

[Enter] Execute  [e] Edit  [c] Cancel  [j] Join session
EOF
            ;;
            
        pattern)
            cat << EOF
Pattern Detected: $PATTERN

Recent output:
----------------
$(echo "$OUTPUT" | tail -20)
----------------

[c] Continue  [a] Abort  [f] Finish  [j] Join session
EOF
            ;;
            
        during)
            cat << EOF
Command Running

Session: $SESSION
Command: $COMMAND

Current output:
----------------
$(echo "$OUTPUT" | tail -30)
----------------

[Enter] Continue waiting  [f] Finish now  [a] Abort  [j] Join
EOF
            ;;
            
        complete)
            cat << EOF
Command Complete

Session: $SESSION
Elapsed: ${TERMTAP_ELAPSED:-unknown}

Final output:
----------------
$(echo "$OUTPUT" | tail -20)
----------------

[Enter] OK  [j] Join session  [r] Rerun
EOF
            ;;
            
        *)
            echo "Unknown mode: $MODE"
            ;;
    esac
}

# Show dialog and capture result
show_dialog() {
    local content_file="$TEMP_DIR/hover-content"
    create_content > "$content_file"
    
    # Use tmux display-popup to show dialog
    tmux display-popup -E -w 80% -h 80% -T "$TITLE" bash -c "
        cat '$content_file'
        echo
        read -n 1 -s choice
        echo \"\$choice\" > '$RESULT_FILE'
        
        # Handle edit mode
        if [[ \"\$choice\" == 'e' && '$MODE' == 'before' ]]; then
            echo
            echo 'Edit command (press Enter when done):'
            read -e -i '$COMMAND' edited_cmd
            echo \"\$edited_cmd\" > '$MESSAGE_FILE'
        fi
    "
    
    # Clean up
    rm -f "$content_file"
}

# Main execution
main() {
    # Ensure temp directory exists
    mkdir -p "$TEMP_DIR"
    
    # Show dialog
    show_dialog
    
    # Read result
    if [[ -f "$RESULT_FILE" ]]; then
        CHOICE=$(cat "$RESULT_FILE")
        rm -f "$RESULT_FILE"
        
        # Output result in parseable format
        echo "CHOICE=$CHOICE"
        
        if [[ -f "$MESSAGE_FILE" ]]; then
            MESSAGE=$(cat "$MESSAGE_FILE")
            rm -f "$MESSAGE_FILE"
            echo "MESSAGE=$MESSAGE"
        fi
        
        exit 0
    else
        echo "CHOICE=cancel"
        exit 1
    fi
}

main "$@"