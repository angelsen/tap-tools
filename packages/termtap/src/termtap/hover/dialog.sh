#!/usr/bin/env bash
#
# termtap hover dialog script
# Interactive dialog for command execution using tmux display-popup
# Provides user interaction for command confirmation, editing, and monitoring
#

set -euo pipefail

# Global constants from environment with defaults
readonly TITLE="${TERMTAP_TITLE:-Command Execution}"
readonly MODE="${TERMTAP_MODE:-before}"
readonly SESSION="${TERMTAP_SESSION:-unknown}"
readonly COMMAND="${TERMTAP_COMMAND:-}"
readonly OUTPUT="${TERMTAP_OUTPUT:-}"
readonly PATTERN="${TERMTAP_PATTERN:-}"
readonly TEMP_DIR="${TERMTAP_TEMP_DIR:-/tmp/termtap}"

# Result file paths
readonly RESULT_FILE="${TEMP_DIR}/hover-result"
readonly MESSAGE_FILE="${TEMP_DIR}/hover-message"

# Clean up old result files
rm -f "${RESULT_FILE}" "${MESSAGE_FILE}"

# Create dialog content based on mode
create_content() {
	case "${MODE}" in
	before)
		cat <<EOF
Execute Command?

Command: ${COMMAND}
Session: ${SESSION}
Directory: $(pwd)

[Enter] Execute  [e] Edit  [c] Cancel  [j] Join session
EOF
		;;

	pattern)
		cat <<EOF
Pattern Detected: ${PATTERN}

Recent output:
----------------
$(echo "${OUTPUT}" | tail -20)
----------------

[c] Continue  [a] Abort  [f] Finish  [j] Join session
EOF
		;;

	during)
		cat <<EOF
Command Running

Session: ${SESSION}
Command: ${COMMAND}

Current output:
----------------
$(echo "${OUTPUT}" | tail -30)
----------------

[Enter] Continue waiting  [f] Finish now  [a] Abort  [j] Join
EOF
		;;

	complete)
		cat <<EOF
Command Complete

Session: ${SESSION}
Elapsed: ${TERMTAP_ELAPSED:-unknown}

Final output:
----------------
$(echo "${OUTPUT}" | tail -20)
----------------

[Enter] OK  [j] Join session  [r] Rerun
EOF
		;;

	*)
		echo "Unknown mode: ${MODE}"
		;;
	esac
}

# Show dialog and capture user input
show_dialog() {
	local content_file="${TEMP_DIR}/hover-content"
	create_content >"${content_file}"

	# Use tmux display-popup to show dialog
	tmux display-popup -E -w 80% -h 80% -T "${TITLE}" bash -c "
        cat '${content_file}'
        echo
        read -n 1 -s choice
        echo \"\${choice}\" > '${RESULT_FILE}'
        
        # Handle edit mode
        if [[ \"\${choice}\" == 'e' && '${MODE}' == 'before' ]]; then
            echo
            echo 'Edit command (press Enter when done):'
            read -e -i '${COMMAND}' edited_cmd
            echo \"\${edited_cmd}\" > '${MESSAGE_FILE}'
        fi
    "

	# Clean up temporary file
	rm -f "${content_file}"
}

# Main execution function
main() {
	# Ensure temp directory exists
	mkdir -p "${TEMP_DIR}"

	# Show dialog to user
	show_dialog

	# Read and process result
	if [[ -f "${RESULT_FILE}" ]]; then
		local choice
		choice=$(cat "${RESULT_FILE}")
		rm -f "${RESULT_FILE}"

		# Output result in parseable format
		echo "CHOICE=${choice}"

		if [[ -f "${MESSAGE_FILE}" ]]; then
			local message
			message=$(cat "${MESSAGE_FILE}")
			rm -f "${MESSAGE_FILE}"
			echo "MESSAGE=${message}"
		fi

		exit 0
	else
		echo "CHOICE=cancel"
		exit 1
	fi
}

main "$@"
