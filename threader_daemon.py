
# import asyncio
# import logging
# import signal
# import sys
# from pathlib import Path
# from dotenv import load_dotenv

# # Add netbot-redacted to path
# sys.path.insert(0, str(Path(__file__).parent))

# from threader.imap import Client  # Changed from IMAPClient to Client

# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# log = logging.getLogger(__name__)

# shutdown_requested = False

# def signal_handler(sig, frame):
#     global shutdown_requested
#     log.info(f"Received signal {sig}, initiating graceful shutdown...")
#     shutdown_requested = True

# async def main():
#     global shutdown_requested
    
#     # Register signal handlers
#     signal.signal(signal.SIGTERM, signal_handler)
#     signal.signal(signal.SIGINT, signal_handler)
    
#     log.info("Starting Threader Daemon")
#     log.info("Processes one email completely, then checks for next")
    
#     # Load environment variables
#     load_dotenv()
    
#     # Create client once
#     client = Client()  # Changed from IMAPClient()
    
#     while not shutdown_requested:
#         try:
#             log.info("Checking IMAP for new messages...")
            
#             # Process emails - this handles ONE email at a time
#             # Returns number of emails processed
#             processed_count = client.synchronize()
            
#             if processed_count > 0:
#                 log.info(f"Processed {processed_count} email(s)")
#                 # Immediately check for next email (no delay after processing)
#                 continue
#             else:
#                 # No emails found - wait 60 seconds before checking again
#                 log.info("No new emails. Waiting 60 seconds before next check...")
#                 await asyncio.sleep(60)
                
#         except KeyboardInterrupt:
#             log.info("Keyboard interrupt received")
#             break
#         except Exception as e:
#             log.error(f"Error in main loop: {e}", exc_info=True)
#             # Wait before retrying on error
#             await asyncio.sleep(60)
    
#     log.info("Threader Daemon stopped")

# if __name__ == "__main__":
#     asyncio.run(main())


#!/usr/bin/env python3
import asyncio
import logging
import signal
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add netbot-redacted to path
sys.path.insert(0, str(Path(__file__).parent))

from threader.imap import Client
from redaction_queue import RedactionQueue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    log.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_requested = True

async def main():
    global shutdown_requested
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    log.info("Starting Threader Daemon")
    log.info("Processes emails and edit requests sequentially")
    
    # Load environment variables
    load_dotenv()
    
    # Create client and queue manager
    client = Client()
    queue = RedactionQueue()
    
    while not shutdown_requested:
        try:
            # Check for edit jobs in queue FIRST (priority)
            edit_job = queue.get_next_job()
            
            if edit_job:
                log.info(f"Processing edit job: {edit_job['id']}")
                queue.mark_processing(edit_job['id'])
                
                try:
                    # Process the edit job
                    client.process_edit_job(edit_job)
                    queue.mark_complete(edit_job['id'])
                    log.info(f"Completed edit job: {edit_job['id']}")
                except Exception as e:
                    log.error(f"Edit job failed: {e}", exc_info=True)
                    queue.mark_failed(edit_job['id'], str(e))
                
                # Immediately check for next job
                continue
            
            # No edit jobs, check IMAP
            log.info("Checking IMAP for new messages...")
            processed_count = client.synchronize()
            
            if processed_count > 0:
                log.info(f"Processed {processed_count} email(s)")
                # Immediately check for next job
                continue
            else:
                # No work to do - wait 60 seconds
                log.info("No pending jobs. Waiting 60 seconds before next check...")
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            log.info("Keyboard interrupt received")
            break
        except Exception as e:
            log.error(f"Error in main loop: {e}", exc_info=True)
            await asyncio.sleep(60)
    
    log.info("Threader Daemon stopped")

if __name__ == "__main__":
    asyncio.run(main())