import os
import time
import threading
import queue # For passing messages to Streamlit
from datetime import datetime # For message timestamps

try:
    print("Attempting to import undetected_chromedriver in kick_scraper.py") # DEBUG PRINT
    from undetected_chromedriver import Chrome, ChromeOptions
    print("Successfully imported undetected_chromedriver") # DEBUG PRINT
except ImportError as e:
    print(f"kick_scraper.py: ImportError for undetected_chromedriver: {e}") # DEBUG PRINT
    # This should ideally be handled by ensuring dependencies are installed before running
    # print("Error: undetected_chromedriver not found. Please install it via pip.")
    raise # Re-raise the exception to make it clear that the import failed


class KickScraper:
    def __init__(self, channel_name, message_queue):
        print(f"KickScraper: Initializing for channel '{channel_name}'") # DEBUG PRINT
        self.channel_name = channel_name
        self.message_queue = message_queue
        self.url = f"https://www.kick.com/{self.channel_name}/chatroom"
        
        self.browser = None
        self.running = False
        self.scraping_thread = None
        self.read_messages_ids = [] # Tracks IDs of messages already processed
        self.interval = 0.2  # Polling interval, increased slightly
        self._stop_event = threading.Event() # For signaling the thread to stop

    def _initialize_browser(self):
        print("KickScraper: Attempting to initialize browser...") # DEBUG PRINT
        try:
            options = ChromeOptions()
            # options.add_argument('--headless') # Optional: run headless
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            # Minimize window - may not work on all systems or with headless
            options.add_argument("--window-size=1,1") 
            options.add_argument("--window-position=-10000,0")


            self.browser = Chrome(use_subprocess=True, options=options)
            # self.browser.set_window_size(1,1) # Alternative way to set size
            self.message_queue.put({"type": "status", "data": "Browser initialized."})
            print("KickScraper: Browser initialized successfully.") # DEBUG PRINT
            return True
        except Exception as e:
            print(f"KickScraper: Failed to initialize browser: {e}") # DEBUG PRINT
            self.message_queue.put({"type": "error", "data": f"Failed to initialize browser: {e}"})
            self.running = False
            return False

    def start(self):
        if self.running:
            self.message_queue.put({"type": "warning", "data": "Scraper is already running."})
            return

        self.running = True
        self._stop_event.clear()
        self.read_messages_ids = [] # Reset read messages on new start

        if not self._initialize_browser():
            return

        self.message_queue.put({"type": "status", "data": f"Attempting to load chatroom: {self.url}"})
        try:
            self.browser.get(self.url)
            time.sleep(3) # Wait for page to potentially load, adjust as needed

            # CAPTCHA check
            if "Checking if the site connection is secure" in self.browser.page_source:
                self.message_queue.put({"type": "status", "data": "CAPTCHA detected. Waiting for it to be resolved..."})
                while "Checking if the site connection is secure" in self.browser.page_source and self.running:
                    if self._stop_event.is_set():
                        self.message_queue.put({"type": "status", "data": "Stop requested during CAPTCHA."})
                        self.running = False
                        break
                    time.sleep(0.5)
                if self.running: # If not stopped during CAPTCHA
                     self.message_queue.put({"type": "status", "data": "CAPTCHA likely passed or page changed."})
            
            if not self.running: # If CAPTCHA wait was interrupted by stop
                self.cleanup()
                return

            self.message_queue.put({"type": "status", "data": f"Chatroom for {self.channel_name} loaded. Starting message polling."})
        except Exception as e:
            self.message_queue.put({"type": "error", "data": f"Error loading chatroom or during CAPTCHA: {e}"})
            self.running = False
            self.cleanup()
            return
            
        self.scraping_thread = threading.Thread(target=self._scrape_messages, daemon=True)
        self.scraping_thread.start()

    def stop(self):
        self.message_queue.put({"type": "status", "data": "Stop requested. Shutting down scraper..."})
        self.running = False
        self._stop_event.set() # Signal the thread to stop

        if self.scraping_thread and self.scraping_thread.is_alive():
            self.scraping_thread.join(timeout=5) # Wait for the thread to finish
            if self.scraping_thread.is_alive():
                 self.message_queue.put({"type": "warning", "data": "Scraping thread did not terminate gracefully."})


        self.cleanup()
        self.message_queue.put({"type": "status", "data": "Scraper stopped."})

    def cleanup(self):
        if self.browser:
            try:
                self.browser.quit()
                self.message_queue.put({"type": "status", "data": "Browser closed."})
            except Exception as e:
                self.message_queue.put({"type": "error", "data": f"Error during browser cleanup: {e}"})
            finally:
                self.browser = None
    
    def _parse_and_queue_messages(self):
        if not self.browser:
            self.running = False # Should not happen if start was successful
            self.message_queue.put({"type": "error", "data": "Browser not available for parsing."})
            return

        try:
            page_source = self.browser.page_source
        except Exception as e: # Handles cases where browser might have crashed or become unresponsive
            self.message_queue.put({"type": "error", "data": f"Failed to get page source: {e}. Stopping scraper."})
            self.running = False
            return

        if "Oops, Something went wrong" in page_source:
            self.message_queue.put({
                "type": "error",
                "data": "Kick.com returned a 404 or similar error. Check channel name (case-sensitive) or channel existence."
            })
            self.running = False # Stop scraping if channel is not found
            return

        if "Checking if the site connection is secure" in page_source:
            self.message_queue.put({"type": "status", "data": "CAPTCHA re-appeared. Pausing polling."})
            # Could implement a timeout here or just wait for next cycle
            return 

        msg_split = page_source.split('data-chat-entry="')
        if not msg_split or len(msg_split) <=1: # No messages or malformed page
            return 
        
        del msg_split[0] # Remove content before the first message

        current_page_messages = []

        for entry_html in msg_split:
            if "chatroom-history-breaker" in entry_html: # Skip history breaker elements
                continue

            try:
                msg_id = entry_html.split('"')[0]
                
                # Extract content
                content_parts = entry_html.split('class="chat-entry-content">')
                if len(content_parts) > 1:
                    # Content might have multiple spans (emotes, text parts)
                    content_html = content_parts[1].split('</div>')[0] # Get content within its div
                    # A more robust way would be to use a proper HTML parser like BeautifulSoup
                    # For now, strip tags crudely. This might miss some nuances.
                    # Example: remove all tags to get text
                    current_msg_content = ""
                    in_tag = False
                    for char_html in content_html:
                        if char_html == '<':
                            in_tag = True
                        elif char_html == '>':
                            in_tag = False
                        elif not in_tag:
                            current_msg_content += char_html
                    current_msg_content = current_msg_content.strip() # Cleaned content
                else:
                    current_msg_content = "" # No content found

                # Extract user_id
                user_id_parts = entry_html.split('data-chat-entry-user-id="')
                if len(user_id_parts) > 1:
                    user_id = user_id_parts[1].split('"')[0]
                else:
                    user_id = "unknown_user_id"
                
                # Extract username
                # Username extraction is tricky as its structure can vary.
                # Looking for the part after style and before </span>
                username_parts = entry_html.split(f'id="{user_id}" style="')
                username = "UnknownUser" # Default
                if len(username_parts) > 1:
                    # Example: ...style="color: #fff;">ActualUsername</span>...
                    # The old logic was: colorCode = v.split('id="' + usrs_ids[-1] + '" style="')[1].split(');">')[0]
                    # usrs.append(v.split(colorCode + ');">')[1].split("</span>")[0])
                    # This is fragile. A more robust CSS selector via Selenium find_element would be better if this fails.
                    # Simplified approach:
                    temp_user_part = username_parts[1].split('">', 1) # Split at the first occurrence of '">'
                    if len(temp_user_part) > 1:
                        username = temp_user_part[1].split("</span>")[0].strip()


                current_page_messages.append({
                    "username": username,
                    "content": current_msg_content,
                    "msg_id": msg_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                })

            except Exception as e:
                # Log parsing error for a single message but continue with others
                self.message_queue.put({"type": "warning", "data": f"Error parsing a message entry: {e}. HTML snippet: {entry_html[:200]}"})
                continue # Skip this message

        # Process new messages
        new_message_count = 0
        for msg_data in reversed(current_page_messages): # Process newest first, or chronologically
            if msg_data["msg_id"] not in self.read_messages_ids:
                self.message_queue.put({"type": "message", "data": msg_data})
                self.read_messages_ids.append(msg_data["msg_id"])
                new_message_count +=1
                # Keep read_messages_ids from growing indefinitely (e.g., keep last 200-500)
                if len(self.read_messages_ids) > 500:
                    self.read_messages_ids.pop(0) 
        
        # if new_message_count > 0:
        #     self.message_queue.put({"type": "status", "data": f"Processed {new_message_count} new message(s)."})


    def _scrape_messages(self):
        self.message_queue.put({"type": "status", "data": "Scraping loop started."})
        while self.running and not self._stop_event.is_set():
            try:
                self._parse_and_queue_messages()
                # Use the event to sleep, so it can be interrupted by stop()
                self._stop_event.wait(self.interval) 
            except Exception as e:
                self.message_queue.put({"type": "error", "data": f"Unhandled error in scraping loop: {e}. Stopping."})
                self.running = False # Stop on critical error
                break # Exit loop
        
        if not self.running and not self._stop_event.is_set():
             self.message_queue.put({"type": "status", "data": "Scraping loop ended due to 'running' flag."})
        elif self._stop_event.is_set():
             self.message_queue.put({"type": "status", "data": "Scraping loop ended due to stop event."})
        # self.cleanup() # Cleanup is now handled by stop()

# Example Usage (for testing scraper independently - not part of Streamlit app)
if __name__ == '__main__':
    print("Starting KickScraper test...")
    test_q = queue.Queue()
    # Replace 'your_channel_name' with a real Kick channel for testing
    scraper = KickScraper("your_channel_name", test_q) 
    scraper.start()

    try:
        # Let it run for a bit to see messages
        for _ in range(60): # Run for approx 60 * interval seconds
            if not scraper.running:
                print("Scraper stopped prematurely during test.")
                break
            while not test_q.empty():
                item = test_q.get()
                print(f"FROM QUEUE: {item}")
                if item.get("type") == "error" and "404" in item.get("data",""):
                    scraper.stop() # Stop if channel error
                    break
            time.sleep(1)
    except KeyboardInterrupt:
        print("Test interrupted by user.")
    finally:
        print("Stopping scraper from test block...")
        scraper.stop()
        print("Test finished.")

    # Drain any remaining messages from the queue
    print("Remaining messages in queue:")
    while not test_q.empty():
        print(test_q.get()) 