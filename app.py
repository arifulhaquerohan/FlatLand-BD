import os

from backend.app import app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    # Debug is opt-in via FLASK_DEBUG=1. Never enable it on a public server:
    # the Werkzeug debugger allows remote code execution.
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
