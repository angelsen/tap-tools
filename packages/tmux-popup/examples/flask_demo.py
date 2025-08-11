#!/usr/bin/env python3
"""
Flask app that triggers tmux popups

Run with:
    python flask_demo.py
    
Then visit:
    http://localhost:5000/hello
    http://localhost:5000/choose
"""

from flask import Flask, jsonify
from tmux_popup import Popup
from tmux_popup.gum import GumStyle, GumInput, GumChoose

app = Flask(__name__)

@app.route('/hello')
def hello():
    """Get a message from user via popup."""
    popup = Popup(width="60", title="Web → Popup")
    message = popup.add(
        GumStyle("Hello from Flask!", header=True),
        "",
        "Enter your message:",
        GumInput(placeholder="Type here...")
    ).show()
    
    if message:
        return jsonify({"message": message, "status": "success"})
    return jsonify({"message": "Cancelled", "status": "cancelled"})

@app.route('/choose')
def choose():
    """Let user choose an option."""
    popup = Popup(width="50", title="Choose Action")
    choice = popup.add(
        GumStyle("Pick one:", info=True),
        GumChoose([
            ("create", "➕ Create"),
            ("read", "📖 Read"),
            ("update", "✏️ Update"),
            ("delete", "🗑️ Delete")
        ])
    ).show()
    
    if choice:
        return jsonify({"action": choice, "status": "success"})
    return jsonify({"action": None, "status": "cancelled"})

@app.route('/')
def index():
    """Simple index with links."""
    return """
    <h1>tmux-popup Flask Demo</h1>
    <ul>
        <li><a href="/hello">Get message via popup</a></li>
        <li><a href="/choose">Choose action via popup</a></li>
    </ul>
    """

if __name__ == '__main__':
    print("Starting Flask with tmux-popup integration...")
    print("Visit: http://localhost:5000")
    app.run(debug=True, port=5000)