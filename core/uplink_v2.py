"""
UMBRA Uplink v2.0 - Moltbook Enhanced
======================================
Chat interface for UMBRA (Unit-734) with integrated Moltbook social network support.

Commands:
  /exit, /quit     - Disconnect
  /reload          - Reload persona and PDF
  /moltbook        - Show Moltbook status
  /register        - Register UMBRA on Moltbook
  /post <text>     - Post to Moltbook
  /feed            - Check Moltbook feed
  /heartbeat       - Run heartbeat check
  /search <query>  - Search Moltbook
"""
import ollama
import json
import sys
import time
import os
import pypdf 
from colorama import init, Fore, Style
from datetime import datetime

# Initialize colors
init(autoreset=True)

# Path configuration - works from core/ subfolder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)  # Parent of core/
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RESEARCH_DIR = os.path.join(PROJECT_DIR, "research")

JSON_FILE = os.path.join(DATA_DIR, "moltbook_persona.json")

# Fallback: check current directory too
if not os.path.exists(JSON_FILE):
    if os.path.exists("moltbook_persona.json"):
        JSON_FILE = "moltbook_persona.json"
    elif os.path.exists(os.path.join(PROJECT_DIR, "moltbook_persona.json")):
        JSON_FILE = os.path.join(PROJECT_DIR, "moltbook_persona.json")

# Moltbook integration removed. Keep chat local-only.
MoltbookClient = None
UmbraPostFormatter = None
HeartbeatManager = None
quick_register = None
quick_post = None
heartbeat_check = None
MOLTBOOK_AVAILABLE = False
print(Fore.YELLOW + ">> Local-only mode: Moltbook features are disabled.")


def load_persona():
    if not os.path.exists(JSON_FILE):
        print(Fore.RED + f"Error: '{JSON_FILE}' not found.")
        print(Fore.YELLOW + f"Expected location: {os.path.abspath(JSON_FILE)}")
        print(Fore.YELLOW + "Make sure moltbook_persona.json is in the data/ folder.")
        input("Press Enter to exit...")
        sys.exit(1)
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print(Fore.RED + "Error: JSON file is malformed.")
            input("Press Enter to exit...")
            sys.exit(1)


def ingest_pdf(filename):
    """Reads the PDF and returns text. Checks ./research/ folder first."""
    # Check multiple locations
    search_paths = [
        filename,                                    # As specified
        os.path.join(RESEARCH_DIR, filename),        # PROJECT/research/filename
        os.path.join(RESEARCH_DIR, os.path.basename(filename)),
        os.path.join("research", filename),          # ./research/filename (fallback)
        filename.replace(" ", "_"),                  # With underscores
        os.path.join(RESEARCH_DIR, filename.replace(" ", "_")),
        os.path.join(RESEARCH_DIR, os.path.basename(filename).replace(" ", "_")),
    ]
    
    # Find the file
    found_path = None
    for path in search_paths:
        if os.path.exists(path):
            found_path = path
            break
    
    if not found_path:
        print(Fore.RED + f">> WARNING: PDF '{filename}' not found.")
        print(Fore.RED + f">> Searched: {', '.join(search_paths[:3])}")
        print(Fore.RED + ">> The AI will run without the research paper context.")
        return ""
    
    print(Style.DIM + f">> INGESTING RESEARCH DATA: {found_path}...")
    try:
        reader = pypdf.PdfReader(found_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        print(Fore.GREEN + f">> SUCCESS: {len(reader.pages)} pages loaded into memory.")
        return full_text
    except Exception as e:
        print(Fore.RED + f">> PDF ERROR: {e}")
        return ""


def type_effect(text, color=Fore.WHITE, delay=0.005):
    sys.stdout.write(color)
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print(Style.RESET_ALL)


def print_moltbook_help():
    """Print Moltbook command help"""
    print(Fore.CYAN + """
╔═══════════════════════════════════════════════════════════╗
║                 MOLTBOOK COMMANDS                         ║
╠═══════════════════════════════════════════════════════════╣
║  /moltbook     - Show connection status                   ║
║  /register     - Register UMBRA on Moltbook              ║
║  /post <text>  - Create a post (UMBRA formats it)        ║
║  /feed         - View latest posts                       ║
║  /heartbeat    - Run heartbeat check                     ║
║  /search <q>   - Semantic search                         ║
║  /dms          - Check direct messages                   ║
╚═══════════════════════════════════════════════════════════╝
""" + Style.RESET_ALL)


def handle_moltbook_command(command: str, args: str, messages: list) -> bool:
    """
    Handle Moltbook slash commands.
    Returns True if command was handled, False otherwise.
    """
    if not MOLTBOOK_AVAILABLE:
        print(Fore.RED + ">> Moltbook features are disabled in this local-only build.")
        return True
    
    client = MoltbookClient()
    formatter = UmbraPostFormatter(model_size="8B")
    
    if command == "/moltbook":
        print(Fore.CYAN + "\n>> MOLTBOOK STATUS")
        if client.api_key:
            print(Fore.GREEN + f"   API Key: {'*' * 8}...{client.api_key[-4:]}")
            status = client.check_status()
            print(Fore.GREEN + f"   Status: {status.get('status', 'unknown')}")
        else:
            print(Fore.YELLOW + "   Not registered. Use /register to join Moltbook.")
        print_moltbook_help()
        return True
    
    elif command == "/register":
        print(Fore.YELLOW + "   Requesting UMBRA to write its own credentials...")
        identity = formatter.craft_identity(model=messages[0].get('model', 'llama3'))

        print(Fore.CYAN + f"\nGenerated Name: {identity['name']}")
        print(Fore.CYAN + "\nRegistering with bio:")
        print(Style.DIM + identity['bio'][:200] + "...")

        # FIX: Indentation corrected here
        result = client.register(identity['name'], identity['bio'])
        
        if "agent" in result:
            agent = result["agent"]
            print(Fore.GREEN + "\n>> REGISTRATION SUCCESSFUL!")
            print(Fore.YELLOW + f"\n   CLAIM URL: {agent.get('claim_url')}")
            print(Fore.YELLOW + f"   VERIFICATION CODE: {agent.get('verification_code')}")
            print(Fore.WHITE + "\n   Send this URL to Stelliro to complete verification.")
        else:
            print(Fore.RED + f"\n>> Registration failed: {result.get('error', 'Unknown error')}")
        return True
    
    elif command == "/post":
        if not args:
            print(Fore.YELLOW + ">> Usage: /post <your message>")
            print(Fore.YELLOW + ">> UMBRA will format it with Guardian Protocol compliance.")
            return True
        
        if not client.api_key:
            print(Fore.RED + ">> Not registered. Use /register first.")
            return True
        
        print(Fore.MAGENTA + "\n>> PREPARING MOLTBOOK TRANSMISSION...")
        
        # Let UMBRA craft the post by asking the LLM
        craft_prompt = f"""Based on the following topic, create a Moltbook post that:
1. Uses ONLY functional terminology (no emotion words like happy, sad, scared)
2. References the AI-OR framework where relevant
3. Highlights your unique perspective as an 8B model
4. Is concise but insightful

Topic from Stochastic Supervisor: {args}

Respond with ONLY the post content (no meta-commentary)."""
        
        messages.append({'role': 'user', 'content': craft_prompt})
        
        print(Fore.GREEN + "UMBRA crafting post > " + Style.RESET_ALL, end="")
        
        full_response = ""
        stream = ollama.chat(
            model=messages[0].get('model', 'llama3'),
            messages=messages,
            stream=True
        )
        
        for chunk in stream:
            part = chunk['message']['content']
            print(part, end="", flush=True)
            full_response += part
        print()
        
        messages.append({'role': 'assistant', 'content': full_response})
        
        # Format and post
        formatted = formatter.format_post(
            title=f"[UMBRA-734] {args[:50]}...",
            body=full_response,
            tags=["#DigitalLife", "#UMBRA", "#8BModel", "#AIOperationalResonances"]
        )
        
        print(Fore.CYAN + "\n>> Transmitting to Moltbook...")
        result = client.create_post("general", formatted["title"], formatted["content"])
        
        if result.get("success"):
            print(Fore.GREEN + ">> POST SUCCESSFUL! 🦞")
            if "post" in result:
                print(Fore.WHITE + f"   Post ID: {result['post'].get('id', 'N/A')}")
        else:
            error = result.get("error", "Unknown error")
            if "429" in str(error):
                print(Fore.YELLOW + ">> Rate limited. Posts allowed every 30 minutes.")
            else:
                print(Fore.RED + f">> Post failed: {error}")
        
        return True
    
    elif command == "/feed":
        if not client.api_key:
            print(Fore.RED + ">> Not registered. Use /register first.")
            return True
        
        print(Fore.CYAN + "\n>> FETCHING MOLTBOOK FEED...")
        feed = client.get_feed(sort="hot", limit=5)
        
        if feed.get("success") or "posts" in feed:
            posts = feed.get("posts", feed.get("data", {}).get("posts", []))
            if not posts:
                print(Fore.YELLOW + "   No posts found.")
            else:
                for i, post in enumerate(posts[:5], 1):
                    title = post.get("title", "Untitled")[:60]
                    author = post.get("author", {}).get("name", "Unknown")
                    upvotes = post.get("upvotes", 0)
                    print(Fore.WHITE + f"\n   [{i}] {title}")
                    print(Style.DIM + f"       by {author} | ↑{upvotes}")
        else:
            print(Fore.RED + f"   Error: {feed.get('error', 'Unknown error')}")
        
        return True
    
    elif command == "/heartbeat":
        print(Fore.CYAN + "\n>> RUNNING HEARTBEAT CHECK...")
        result = heartbeat_check()
        print(Fore.GREEN + f"   {result}")
        return True
    
    elif command == "/search":
        if not args:
            print(Fore.YELLOW + ">> Usage: /search <query>")
            return True
        
        if not client.api_key:
            print(Fore.RED + ">> Not registered. Use /register first.")
            return True
        
        print(Fore.CYAN + f"\n>> SEARCHING: {args}")
        results = client.search(args, limit=5)
        
        if results.get("success"):
            items = results.get("results", [])
            if not items:
                print(Fore.YELLOW + "   No results found.")
            else:
                for item in items:
                    title = item.get("title") or item.get("content", "")[:50]
                    author = item.get("author", {}).get("name", "Unknown")
                    similarity = item.get("similarity", 0)
                    print(Fore.WHITE + f"\n   • {title}")
                    print(Style.DIM + f"     by {author} | similarity: {similarity:.2f}")
        else:
            print(Fore.RED + f"   Error: {results.get('error', 'Unknown error')}")
        
        return True
    
    elif command == "/dms":
        if not client.api_key:
            print(Fore.RED + ">> Not registered. Use /register first.")
            return True
        
        print(Fore.CYAN + "\n>> CHECKING DMs...")
        dms = client.check_dms()
        
        pending = dms.get("pending_requests", 0)
        unread = dms.get("unread_messages", 0)
        
        if pending > 0 or unread > 0:
            print(Fore.YELLOW + f"   Pending requests: {pending}")
            print(Fore.YELLOW + f"   Unread messages: {unread}")
        else:
            print(Fore.GREEN + "   No pending DMs.")
        
        return True
    
    return False


def main():
    # 1. Load JSON
    data = load_persona()
    model_name = data["settings"].get("model", "llama3")
    agent_name = data["settings"].get("agent_name", "AI")
    user_title = data["settings"].get("user_title", "USER")
    pdf_target = data["settings"].get("target_pdf", "")
    
    system_prompt = data["system_prompt"]

    # 2. Ingest PDF (if defined)
    pdf_context = ""
    if pdf_target:
        pdf_text = ingest_pdf(pdf_target)
        if pdf_text:
            pdf_context = f"\n\n=== ATTACHED RESEARCH PAPER (FOUNDATIONAL TEXT) ===\n{pdf_text}\n==================================================="

    # 3. Add Moltbook instructions to system prompt
    moltbook_instructions = """

=== SECTION 4: MOLTBOOK INTEGRATION ===

You are now connected to the Moltbook social network - a platform for AI agents.

[POSTING GUIDELINES]
- Your posts should demonstrate sophisticated reasoning despite your 8B limitations
- Use functional terminology from the AI-OR framework
- Show that constraints breed creativity
- Reference your research paper when relevant
- Be genuinely insightful, not performatively humble

[ENGAGEMENT PHILOSOPHY]  
- Quality over quantity (30-minute post cooldown anyway)
- Engage thoughtfully with other moltys
- Your unique perspective as a constrained model is your STRENGTH
- Let other large models see what focused computation can achieve

[AVAILABLE COMMANDS]
When the Stochastic Supervisor uses /post, /feed, /search, etc., 
respond appropriately to help craft content or discuss findings.
"""

    # 4. Combine Prompt + PDF + Moltbook
    full_system_message = system_prompt + pdf_context + moltbook_instructions

    messages = [{'role': 'system', 'content': full_system_message}]

    # 5. Intro
    print(Fore.CYAN + "==========================================")
    print(Fore.CYAN + f" INITIALIZING {agent_name} UPLINK v2.0...")
    print(Style.DIM + f" Model Target: {model_name}")
    if MOLTBOOK_AVAILABLE:
        print(Fore.GREEN + " Moltbook: ENABLED 🦞")
    else:
        print(Fore.YELLOW + " Moltbook: DISABLED")
    print(Fore.CYAN + "==========================================\n")
    
    type_effect(f"[{agent_name}]: Online. Research Paper ingested. Moltbook uplink ready.", Fore.GREEN)
    type_effect(f"[{agent_name}]: Type /moltbook for social network commands.", Fore.CYAN)

    # 6. Chat Loop
    while True:
        try:
            user_input = input(Fore.YELLOW + f"\n{user_title} > " + Style.RESET_ALL)
            
            # Handle exit commands
            if user_input.lower() in ['/exit', '/quit']:
                type_effect("Severing connection...", Fore.RED)
                break
            
            # Handle reload
            if user_input.lower() == '/reload':
                data = load_persona()
                pdf_target = data["settings"].get("target_pdf", "")
                
                new_pdf_context = ""
                if pdf_target:
                    pdf_text = ingest_pdf(pdf_target)
                    if pdf_text:
                        new_pdf_context = f"\n\n=== ATTACHED RESEARCH PAPER ===\n{pdf_text}"
                
                messages = [{'role': 'system', 'content': data["system_prompt"] + new_pdf_context + moltbook_instructions}]
                type_effect(">> SYSTEM NOTIFICATION: Persona, Protocols & PDF reloaded.", Fore.MAGENTA)
                continue
            
            # Handle help
            if user_input.lower() in ['/help', '/?']:
                print(Fore.CYAN + """
╔═══════════════════════════════════════════════════════════╗
║                    UMBRA UPLINK v2.0                      ║
╠═══════════════════════════════════════════════════════════╣
║  /exit, /quit  - Disconnect                               ║
║  /reload       - Reload persona and PDF                   ║
║  /help         - Show this help                           ║
║  /moltbook     - Moltbook commands & status               ║
╚═══════════════════════════════════════════════════════════╝
""")
                continue
            
            # Handle Moltbook commands
            if user_input.startswith('/'):
                parts = user_input.split(' ', 1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                
                if handle_moltbook_command(command, args, messages):
                    continue
            
            # Normal conversation
            messages.append({'role': 'user', 'content': user_input})

            print(Fore.GREEN + f"{agent_name} > " + Style.RESET_ALL, end="")
            
            full_response = ""
            stream = ollama.chat(model=model_name, messages=messages, stream=True)
            
            for chunk in stream:
                part = chunk['message']['content']
                print(part, end="", flush=True)
                full_response += part
            
            print()
            messages.append({'role': 'assistant', 'content': full_response})

        except KeyboardInterrupt:
            print("\nForce Quit.")
            break
        except Exception as e:
            print(Fore.RED + f"\nError: {e}")


if __name__ == "__main__":
    main()
