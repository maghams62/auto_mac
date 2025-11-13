# Tool Definitions

Complete specification of available tools for the automation agent.

**Generated from tool catalog analysis.**

**CRITICAL INSTRUCTIONS FOR TOOL USAGE:**
1. **Tool Validation**: Before using ANY tool, verify it exists in this list
2. **Parameter Requirements**: All REQUIRED parameters must be provided
3. **Type Safety**: Match parameter types exactly (string, int, list, etc.)
4. **Error Handling**: Check return values for "error": true field
5. **Early Rejection**: If a needed tool doesn't exist, reject the task immediately with complexity="impossible"

---

## BLUESKY Agent (4 tools)

### search_bluesky_posts
**Description:** Search Bluesky for recent posts matching a query.
**Parameters:**
- `query` (string, required): The search query
- `max_posts` (integer, required): Maximum number of posts to return

### get_bluesky_author_feed
**Description:** Get posts from a specific Bluesky author/handle. If actor is None, gets posts from authenticated user.
**Parameters:**
- `actor` (string): The Bluesky handle to get posts from
- `max_posts` (integer, required): Maximum number of posts to return

### summarize_bluesky_posts
**Description:** Gather and summarize top Bluesky posts for a query or from a specific author within an optional time window.
**Parameters:**
- `query` (string): The search query
- `lookback_hours` (integer): Number of hours to look back
- `max_items` (integer): Maximum number of items to summarize
- `actor` (string): Specific author handle

### post_bluesky_update
**Description:** Publish a status update to Bluesky using the configured account.
**Parameters:**
- `message` (string, required): The message to post

---

## KNOWLEDGE Agent (1 tool)

### wiki_lookup
**Description:** Look up factual information on Wikipedia with fast API access and caching. LEVEL 1 tool - use FIRST for factual overviews, background information, and quick references.
**Parameters:**
- `query` (string, required): The topic, person, place, or concept to look up on Wikipedia (e.g., "Python programming language", "Albert Einstein", "World War II")

**Returns:**
- `title` (string): Article title
- `summary` (string): Brief summary/extract from the article
- `url` (string): Full Wikipedia URL to the article
- `confidence` (float): Confidence score (0.0-1.0, 1.0 = good match)
- `error` (boolean): Whether an error occurred
- `error_type` (string): Error type if error=True ("NotFound", "Timeout", etc.)
- `error_message` (string): Error description if error=True

---

## BROWSER Agent (4 tools)

### navigate_to_url
**Description:** Navigate to a specific URL. LEVEL 2 tool - use after google_search to visit specific pages.
**Parameters:**
- `url` (string, required): The URL to navigate to
- `wait_until` (string, required): When to consider navigation complete

### extract_page_content
**Description:** Extract clean text content from webpages using langextract. LEVEL 2 tool - use for reading and analyzing webpage content.
**Parameters:**
- `url` (string): URL to extract from (if not current page)

### take_web_screenshot
**Description:** Capture webpage screenshots. LEVEL 3 tool - use when you need visual proof or reference of webpage content.
**Parameters:**
- `url` (string): URL to screenshot (if not current page)
- `full_page` (boolean): Whether to capture full page or just viewport

### close_browser
**Description:** Close browser and clean up resources. LEVEL 4 tool - use at the end of web browsing sessions.
**Parameters:** None

---

## CRITIC Agent (4 tools)

### verify_information
**Description:** Verify information accuracy using multiple sources and reasoning.
**Parameters:**
- `claim` (string, required): The information to verify
- `context` (string): Additional context for verification

### validate_logic
**Description:** Validate logical consistency and reasoning in plans or arguments.
**Parameters:**
- `logic` (string, required): The logic or plan to validate
- `context` (string): Context for the validation

### check_completeness
**Description:** Check if a task or plan is complete and comprehensive.
**Parameters:**
- `task` (string, required): The task or plan to check
- `requirements` (list): List of requirements to check against

### identify_risks
**Description:** Identify potential risks and failure points in plans or actions.
**Parameters:**
- `plan` (string, required): The plan to analyze for risks
- `context` (string): Additional context

---

## EMAIL Agent (6 tools)

### compose_email
**Description:** Compose and send emails via Mail.app
**Parameters:**
- `subject` (string, required): Email subject
- `body` (string, required): Email body
- `recipient` (string): Email recipient
- `attachments` (list): List of file paths to attach
- `send` (boolean, required): Whether to send immediately

### reply_to_email
**Description:** Reply to an existing email thread
**Parameters:**
- `original_email_id` (string, required): ID of email to reply to
- `body` (string, required): Reply body
- `attachments` (list): List of file paths to attach

### forward_email
**Description:** Forward an existing email
**Parameters:**
- `original_email_id` (string, required): ID of email to forward
- `recipients` (list, required): List of recipients to forward to
- `additional_message` (string): Additional message to include

### search_emails
**Description:** Search through email messages
**Parameters:**
- `query` (string, required): Search query
- `max_results` (integer): Maximum results to return

### get_email_details
**Description:** Get detailed information about a specific email
**Parameters:**
- `email_id` (string, required): ID of the email to retrieve

### archive_email
**Description:** Archive or organize emails
**Parameters:**
- `email_ids` (list, required): List of email IDs to archive
- `folder` (string): Target folder for archiving

---

## FILE Agent (9 tools)

### read_file
**Description:** Read contents of a file
**Parameters:**
- `target_file` (string, required): Path to the file to read
- `offset` (integer): Line number to start reading from
- `limit` (integer): Number of lines to read

### write_file
**Description:** Write content to a file
**Parameters:**
- `file_path` (string, required): Path to the file to write
- `contents` (string, required): Content to write

### edit_file
**Description:** Edit existing file content
**Parameters:**
- `file_path` (string, required): Path to the file to edit
- `old_string` (string, required): Text to replace
- `new_string` (string, required): Replacement text

### list_directory
**Description:** List files and directories in a path
**Parameters:**
- `target_directory` (string, required): Directory path to list

### create_directory
**Description:** Create a new directory
**Parameters:**
- `path` (string, required): Path for the new directory

### delete_file
**Description:** Delete a file
**Parameters:**
- `target_file` (string, required): Path to the file to delete

### copy_file
**Description:** Copy a file from one location to another
**Parameters:**
- `source_path` (string, required): Source file path
- `destination_path` (string, required): Destination file path

### move_file
**Description:** Move a file from one location to another
**Parameters:**
- `source_path` (string, required): Source file path
- `destination_path` (string, required): Destination file path

### get_file_info
**Description:** Get metadata about a file
**Parameters:**
- `file_path` (string, required): Path to the file

---

## FOLDER Agent (11 tools)

### create_folder
**Description:** Create a new folder/directory
**Parameters:**
- `path` (string, required): Path for the new folder

### delete_folder
**Description:** Delete a folder/directory
**Parameters:**
- `path` (string, required): Path to the folder to delete

### list_folder_contents
**Description:** List contents of a folder
**Parameters:**
- `path` (string, required): Path to the folder
- `recursive` (boolean): Whether to list recursively

### move_folder
**Description:** Move a folder to a new location
**Parameters:**
- `source_path` (string, required): Source folder path
- `destination_path` (string, required): Destination folder path

### copy_folder
**Description:** Copy a folder to a new location
**Parameters:**
- `source_path` (string, required): Source folder path
- `destination_path` (string, required): Destination folder path

### rename_folder
**Description:** Rename a folder
**Parameters:**
- `path` (string, required): Current folder path
- `new_name` (string, required): New folder name

### get_folder_size
**Description:** Calculate total size of a folder
**Parameters:**
- `path` (string, required): Path to the folder

### sync_folders
**Description:** Synchronize contents between folders
**Parameters:**
- `source_path` (string, required): Source folder path
- `destination_path` (string, required): Destination folder path

### compress_folder
**Description:** Compress a folder into an archive
**Parameters:**
- `path` (string, required): Path to the folder to compress
- `archive_path` (string, required): Path for the archive file

### search_in_folder
**Description:** Search for files in a folder
**Parameters:**
- `path` (string, required): Folder path to search in
- `query` (string, required): Search query

### organize_folder
**Description:** Organize files in a folder by type or date
**Parameters:**
- `path` (string, required): Path to the folder to organize

---

## GOOGLE Agent (3 tools)

### google_search
**Description:** Perform DuckDuckGo web searches and extract structured results. LEVEL 1 tool in browser hierarchy—use this first when you need to find information on the web.
**Parameters:**
- `query` (string, required): The search query
- `num_results` (integer, required): Number of results to return

---

## GOOGLE FINANCE Agent (4 tools)

### get_stock_quote
**Description:** Get current stock quote information
**Parameters:**
- `symbol` (string, required): Stock symbol (e.g., AAPL, GOOGL)

### get_stock_history
**Description:** Get historical stock price data
**Parameters:**
- `symbol` (string, required): Stock symbol
- `period` (string): Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

### get_market_summary
**Description:** Get market summary and indices
**Parameters:** None

### analyze_stock
**Description:** Analyze stock performance and provide insights
**Parameters:**
- `symbol` (string, required): Stock symbol to analyze

---

## IMESSAGE Agent (1 tools)

### send_imessage
**Description:** Send iMessage to a contact
**Parameters:**
- `recipient` (string, required): Phone number or email of recipient
- `message` (string, required): Message content

---

## MAPS Agent (5 tools)

### get_directions
**Description:** Get driving directions between locations
**Parameters:**
- `origin` (string, required): Starting location
- `destination` (string, required): Ending location

### get_transit_schedule
**Description:** Get public transit schedule information
**Parameters:**
- `location` (string, required): Location to get transit info for
- `route` (string): Specific route or line

### plan_trip_with_stops
**Description:** Plan a road trip with fuel and food stops. ALL parameters must be extracted from user's natural language query using LLM reasoning.
**Parameters:**
- `origin` (string, required): Trip starting point
- `destination` (string, required): Trip ending point
- `num_fuel_stops` (integer, required): Number of fuel stops
- `num_food_stops` (integer, required): Number of food stops
- `departure_time` (string): Planned departure time
- `use_google_maps` (boolean): Whether to use Google Maps instead of Apple Maps
- `open_maps` (boolean): Whether to open Maps app automatically

### open_maps_with_route
**Description:** Open Apple Maps application with a specific route. Use after plan_trip_with_stops to display the route in Maps app.
**Parameters:**
- `origin` (string, required): Starting location
- `destination` (string, required): Ending location
- `stops` (list): List of intermediate stops

### get_google_transit_directions
**Description:** Get transit directions using Google Maps (with real-time data)
**Parameters:**
- `origin` (string, required): Starting location
- `destination` (string, required): Ending location
- `mode` (string): Transit mode (bus, subway, train, etc.)

---

## MICRO ACTIONS Agent (3 tools)

### run_terminal_command
**Description:** Execute terminal/shell commands
**Parameters:**
- `command` (string, required): Command to execute
- `is_background` (boolean): Whether to run in background

### open_application
**Description:** Open a macOS application
**Parameters:**
- `app_name` (string, required): Name of application to open

### take_screenshot
**Description:** Take a screenshot of the screen
**Parameters:**
- `region` (object): Specific region to capture

---

## NOTIFICATIONS Agent (1 tools)

### send_notification
**Description:** Send a system notification
**Parameters:**
- `title` (string, required): Notification title
- `message` (string, required): Notification message
- `sound` (string): Notification sound to play

---

## PRESENTATION Agent (3 tools)

### create_keynote
**Description:** Create Keynote presentations from text content
**Parameters:**
- `title` (string, required): Presentation title
- `content` (string, required): Content for the presentation
- `output_path` (string): Path to save the presentation

### create_keynote_with_images
**Description:** Create Keynote presentations with images/screenshots as slides. Use this when user wants to display screenshots or images in a presentation.
**Parameters:**
- `title` (string, required): Presentation title
- `image_paths` (list, required): List of image file paths
- `output_path` (string): Path to save the presentation

### create_pages_doc
**Description:** Create Pages documents from content
**Parameters:**
- `title` (string, required): Document title
- `content` (string, required): Document content
- `output_path` (string): Path to save the document

---

## REDDIT Agent (1 tools)

### search_reddit
**Description:** Search Reddit posts and comments
**Parameters:**
- `query` (string, required): Search query
- `subreddit` (string): Specific subreddit to search in
- `max_results` (integer): Maximum results to return

---

## REPORT Agent (2 tools)

### generate_report
**Description:** Generate structured reports from data
**Parameters:**
- `title` (string, required): Report title
- `data` (object, required): Data to include in report
- `format` (string): Report format (PDF, HTML, etc.)

### export_report
**Description:** Export reports to various formats
**Parameters:**
- `report_id` (string, required): ID of report to export
- `format` (string, required): Export format
- `output_path` (string, required): Path to save exported report

---

## SCREEN Agent (1 tools)

### get_screen_info
**Description:** Get information about screen/display configuration
**Parameters:** None

---

## STOCK Agent (5 tools)

### get_stock_price
**Description:** Get current stock price
**Parameters:**
- `ticker` (string, required): Stock ticker symbol

### get_stock_chart
**Description:** Generate stock price chart
**Parameters:**
- `ticker` (string, required): Stock ticker symbol
- `period` (string): Time period for chart

### get_stock_news
**Description:** Get news articles about a stock
**Parameters:**
- `ticker` (string, required): Stock ticker symbol
- `max_articles` (integer): Maximum number of articles

### analyze_portfolio
**Description:** Analyze stock portfolio performance
**Parameters:**
- `holdings` (list, required): List of stock holdings with quantities

### track_stock
**Description:** Set up tracking for stock price alerts
**Parameters:**
- `ticker` (string, required): Stock ticker symbol
- `alert_price` (number): Price threshold for alerts

---

## TWITTER Agent (2 tools)

### search_tweets
**Description:** Search for tweets matching criteria
**Parameters:**
- `query` (string, required): Search query
- `max_results` (integer): Maximum tweets to return

### post_tweet
**Description:** Post a tweet
**Parameters:**
- `content` (string, required): Tweet content
- `reply_to` (string): ID of tweet to reply to

---

## VOICE Agent (2 tools)

### text_to_speech
**Description:** Convert text to speech
**Parameters:**
- `text` (string, required): Text to convert
- `voice` (string): Voice to use
- `speed` (number): Speech speed

### speech_to_text
**Description:** Convert speech/audio to text
**Parameters:**
- `audio_path` (string, required): Path to audio file
- `language` (string): Language of the audio

---

## WRITING Agent (10 tools)

### prepare_writing_brief
**Description:** Analyze user request and context to create a structured writing brief.
**Parameters:**
- `user_request` (string, required): The original user request
- `deliverable_type` (string, required): Type of content to create
- `upstream_artifacts` (object): Results from prior steps
- `context_hints` (object): Additional context
- `session_context` (object): Session context for auto-population

### create_quick_summary
**Description:** Create brief, conversational summaries
**Parameters:**
- `content` (string, required): Content to summarize
- `writing_brief` (object): Writing brief for tone matching

### synthesize_content
**Description:** Synthesize information from multiple sources into cohesive content.
**Parameters:**
- `source_contents` (list, required): List of text contents to synthesize
- `topic` (string): The main topic or focus for synthesis
- `synthesis_style` (string, required): How to synthesize (comprehensive, concise, comparative, chronological)
- `writing_brief` (object): Optional writing brief as dictionary
- `session_context` (object): Optional SessionContext for auto-populating topic

### create_slide_deck_content
**Description:** Transform content into presentation slides
**Parameters:**
- `content` (string, required): Content to transform
- `writing_brief` (object): Writing brief for data-driven decks

### create_detailed_report
**Description:** Create comprehensive long-form reports
**Parameters:**
- `topic` (string, required): Report topic
- `writing_brief` (object): Writing brief for targeted reports

### create_meeting_notes
**Description:** Structure meeting notes with action items
**Parameters:**
- `meeting_content` (string, required): Raw meeting content
- `participants` (list): List of meeting participants

### compose_professional_email
**Description:** Compose professional emails
**Parameters:**
- `recipient` (string, required): Email recipient
- `subject` (string, required): Email subject
- `purpose` (string, required): Email purpose
- `key_points` (list, required): Key points to include

### chain_of_density_summarize
**Description:** Create dense summaries using chain-of-density technique
**Parameters:**
- `content` (string, required): Content to summarize
- `topic` (string): Topic focus
- `max_rounds` (integer): Maximum refinement rounds

### plan_slide_skeleton
**Description:** Plan presentation slide structure before creation
**Parameters:**
- `topic` (string, required): Presentation topic
- `objectives` (list, required): Presentation objectives
- `audience` (string, required): Target audience

### self_refine
**Description:** Iteratively refine written content for quality
**Parameters:**
- `content` (string, required): Content to refine
- `criteria` (list, required): Refinement criteria

---

## VISION Agent (3 tools)

### analyze_image
**Description:** Analyze image content using computer vision
**Parameters:**
- `image_path` (string, required): Path to image file

### extract_text_from_image
**Description:** Extract text from images using OCR
**Parameters:**
- `image_path` (string, required): Path to image file

### describe_image
**Description:** Generate natural language description of image
**Parameters:**
- `image_path` (string, required): Path to image file

---

## WHATSAPP Agent (2 tools)

### send_whatsapp_message
**Description:** Send WhatsApp message
**Parameters:**
- `recipient` (string, required): Recipient phone number
- `message` (string, required): Message content

### read_whatsapp_messages
**Description:** Read WhatsApp messages
**Parameters:**
- `limit` (integer): Maximum messages to read

---

## REPLY Agent (1 tools)

### reply_to_user
**Description:** Compose the final user-facing reply with optional details and artifacts.
**Parameters:**
- `message` (string, required): Main response message
- `details` (string): Additional details
- `artifacts` (list): List of artifact file paths
- `status` (string, required): Response status

---

## SPOTIFY Agent (3 tools)

### play_song
**Description:** Play a song on Spotify
**Parameters:**
- `query` (string, required): Song name or search query

### pause_playback
**Description:** Pause current Spotify playback
**Parameters:** None

### resume_playback
**Description:** Resume Spotify playback
**Parameters:** None

---

## WEATHER Agent (2 tools)

### get_current_weather
**Description:** Get current weather conditions
**Parameters:**
- `location` (string, required): Location for weather

### get_weather_forecast
**Description:** Get weather forecast
**Parameters:**
- `location` (string, required): Location for forecast
- `days` (integer): Number of days for forecast

---

## NOTES Agent (2 tools)

### create_note
**Description:** Create a new note
**Parameters:**
- `title` (string, required): Note title
- `content` (string, required): Note content

### search_notes
**Description:** Search through notes
**Parameters:**
- `query` (string, required): Search query

---

## REMINDERS Agent (2 tools)

### create_reminder
**Description:** Create a new reminder
**Parameters:**
- `title` (string, required): Reminder title
- `due_date` (string): Due date for reminder

### list_reminders
**Description:** List active reminders
**Parameters:** None

---

## CALENDAR Agent (3 tools)

### create_event
**Description:** Create a calendar event
**Parameters:**
- `title` (string, required): Event title
- `start_time` (string, required): Event start time
- `duration` (integer): Event duration in minutes

### list_events
**Description:** List calendar events
**Parameters:**
- `date` (string): Date to list events for

### delete_event
**Description:** Delete a calendar event
**Parameters:**
- `event_id` (string, required): ID of event to delete

---

## DAILY_OVERVIEW Agent (2 tools)

### generate_daily_overview
**Description:** Generate a daily overview report
**Parameters:**
- `date` (string): Date for overview (defaults to today)

### get_productivity_metrics
**Description:** Get productivity metrics for a period
**Parameters:**
- `start_date` (string, required): Start date
- `end_date` (string, required): End date

---

## CELEBRATION Agent (1 tools)

### trigger_celebration
**Description:** Trigger a celebration animation or effect
**Parameters:**
- `type` (string): Type of celebration (success, achievement, etc.)

---
