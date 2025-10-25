Command-line Reversi that discovers a peer on the local network via UDP broadcast and plays over TCP. One codebase acts as either Player 1 (Black) or Player 2 (White).

Prerequisites

Python 3.10+ (tested on 3.10–3.13; Windows/macOS/Linux)

No third-party dependencies required (pytest optional for tests)

Optional virtual environment:
Windows: .venv\Scripts\activate
macOS/Linux: source .venv/bin/activate

Install
Nothing to install for runtime. If running tests, you can pip install -r requirements.txt (contains pytest).

How to run

A) Local hotseat (no networking)
Run: python -m reversi.main --hotseat --verbose
Two humans on one terminal; only valid moves are offered.

B) Network play (UDP matchmaking + TCP gameplay)
Open two terminals (same machine or LAN), then run in both:
python -m reversi.main --play --broadcast-addr 255.255.255.255 --broadcast-port 9000 --verbose

What happens:

The program cycles in 5-second listen windows and 5-second advertise windows until it pairs.

One instance becomes P1 (BLACK), the other P2 (WHITE), and the game begins.
If pairing doesn’t happen, allow Python through your firewall, try a different broadcast port in 9000–9100 (for example, --broadcast-port 9001), or run both terminals on the same machine. Using your subnet-directed broadcast (e.g., 192.168.1.255) can also help on some networks.

Note on coordinates on the wire: TCP MOVE is 0-based: “MOVE:row,col” where row and col are in 0..7.

Assumptions for this assignmen
“How to run: broadcast address and port are required for network play; hotseat is available.”

“UDP matchmaking: 5-second listen and 5-second advertise windows, looping.”

“Wire coordinates are 0-based (0..7) even though the UI shows algebraic.”

“Outcome tokens are peer-addressed (if I’m winning, I send YOU LOSE to you).”

“ERROR is sent on malformed/illegal messages; receiving ERROR causes both clients to exit.”

“Networking assumption: same machine or same L2 LAN; subnet broadcast like 192.168.1.255 can be used if 255.255.255.255 is filtered.”

Statement of Generative AI Use
Chatgpt was used to help break down the problem into actionable steps as well as research
Coding was conducted by myself as well as allowing vscode copilot to auto complete methods where applicable and non applicable

Key Prompts used in chat gpt
"i want you to break down this assignment into incremental steps that i will action in a prompt per step and you will provide feedback and test cases"
Response: Awesome brief. Here’s a clean, incremental plan you can run step-by-step. Each step has: goal, what to build, acceptance criteria, and a copy-paste prompt you can give me when you’re ready for that step. I’ll default to Python (fastest for sockets + CLI), but I can translate to Java/C#/JS at any point... then the 13 step plan to do so 