import subprocess
import os
import time
import argparse

# List of all bot folders
BOTS_DIR = "bots"
bots = [d for d in os.listdir(BOTS_DIR) if os.path.isdir(os.path.join(BOTS_DIR, d))]

def run_bot(bot_name, mode="updates", max_pages=5):
    script_path = os.path.join(BOTS_DIR, bot_name, "run.py")
    if os.path.exists(script_path):
        print(f"============================================================")
        print(f"🚀 Starting Bot: {bot_name} (Mode: {mode})")
        print(f"============================================================")
        try:
            cmd = ["python3", script_path, "--mode", mode]
            if mode == "full":
                cmd.extend(["--max-pages", str(max_pages)])
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Error running bot {bot_name}: {e}")
        print(f"✅ Finished Bot: {bot_name}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Central Bot Runner")
    parser.add_argument("--mode", choices=["full", "updates"], default="updates", help="Scraping mode")
    parser.add_argument("--pages", type=int, default=1, help="Max pages per bot in full mode")
    args = parser.parse_args()

    print(f"🌟 Starting All Bots (Total: {len(bots)}) in {args.mode} mode")
    for bot in bots:
        run_bot(bot, mode=args.mode, max_pages=args.pages)
        time.sleep(2)
    print("🏁 All bots have finished their cycle.")
