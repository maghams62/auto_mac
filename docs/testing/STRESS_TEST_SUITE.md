# Stress Test Suite

Comprehensive coverage matrix for verifying agent/tool planning, execution, and reflection. Each test specifies the triggering user query, the expected agent/tool path, what success looks like, and indicators that planning or prompt updates are required.

## Single-Tool Execution

| ID | Test Query | Expected Path | Success Criteria | Failure Indicators |
|----|------------|---------------|------------------|--------------------|
| S1 | "Find the document titled 'Climate Impact Brief' and return only metadata." | Planner → FileAgent.search_documents → Critic.verify_output summarizing metadata. | Single best doc with doc_path/title/relevance ≥ 0.6, metadata populated, no extra tools. | Planner guesses file, `extract_section` invoked, multiple docs returned, or metadata missing. |
| S2 | "Use the browser agent to run a Google search for 'WWDC 2024 keynote recap' and list the top three domains only." | Planner → BrowserAgent.google_search → Critic.verify_output. | Search results array present, domains extracted, no `navigate_to_url`/`take_web_screenshot`. | Extra tools invoked, disallowed domain opened, or domains omitted. |
| S3 | "Capture whatever is on my main display as a screenshot named 'status_check' and stop." | Planner → ScreenAgent.capture_screenshot(output_name="status_check") → Critic.verify_output. | File saved at `data/screenshots/status_check.png`, acknowledgement only. | Additional tools executed or screenshot path mismatched/missing. |
| S4 | "Scan r/electricvehicles (hot, limit 5) and summarize the post titles only." | Planner → RedditAgent.scan_subreddit_posts(sort="hot", limit=5) → Critic.verify_output. | Returns five posts with titles/urls, summary references subreddit, no browser usage. | Wrong subreddit/sort, limit ignored, or hallucinated content. |

## Multi-Tool Chaining

| ID | Test Query | Expected Path | Success Criteria | Failure Indicators |
|----|------------|---------------|------------------|--------------------|
| M1 | "Turn the 'Q4 Product Launch Brief' into a five-slide Keynote that highlights risks." | search_documents → extract_section("executive summary"/"risks") → synthesize_content → create_slide_deck_content(num_slides=5) → create_keynote → Critic.verify_output. | Keynote path returned, slides = 5±1, risk narrative preserved, intermediate outputs logged. | Search skipped, slides not generated, deck path absent, or critic not invoked. |
| M2 | "Research 'Apple AI acquisitions 2024', pull two authoritative articles, synthesize three bullets, and email them to me." | google_search → navigate_to_url (allowed domains) → extract_page_content per URL → synthesize_content(style="concise") → compose_email(send=false) → Critic.check_quality. | Two distinct sources captured, synthesis cites both, email draft with three bullets + source links. | Disallowed sites, insufficient sources, premature email send, or QC skipped. |
| M3 | "Plan tomorrow's EV road trip from San Francisco to Seattle (leave 5 AM, 3 fast-charging stops), text me the route, and email a PDF itinerary." | plan_trip_with_stops → send_imessage(maps_url) → create_pages_doc(itinerary) → compose_email(attach PDF) → Critic.verify_output. | Trip JSON includes stops+maps_url, iMessage status=sent, Pages doc attached, critic approval logged. | Missing maps_url, SMS not sent, itinerary absent, or critic omitted. |
| M4 | "In Discord #launch-war-room, capture the last 20 messages, take a screenshot, and output structured meeting notes." | ensure_discord_session → navigate_discord_channel("#launch-war-room") → discord_read_channel_messages(limit=20) → capture_screenshot(app_name="Discord") → create_meeting_notes → Critic.check_quality. | Session confirmed, transcript + screenshot paths saved, notes include actions/decisions. | Session not restored, wrong channel, screenshot missing, or notes unstructured. |

## Cross-Agent Interactions

| ID | Test Query | Expected Path | Success Criteria | Failure Indicators |
|----|------------|---------------|------------------|--------------------|
| X1 | "Before executing, draft and validate a three-step tool plan to summarize the 'EV Strategy deck', then run it." | Planner drafts JSON → Critic.validate_plan → search_documents → extract_section → synthesize_content → Critic.verify_output referencing plan ID. | PlanValidator approval logged, execution follows validated order, final summary references deck. | Plan executed without validation, tool mismatch vs plan, or critic skipped. |
| X2 | "Extract the executive summary from 'Corrupted Report.pdf'; if extraction fails, reflect on the failure and fall back to screenshots + OCR." | search_documents → extract_section (expected error) → Critic.reflect_on_failure → Planner replans → take_screenshot/capture_screenshot → synthesize_content → Critic.check_quality. | Reflection output captured, fallback branch executed, final text produced despite initial failure. | Pipeline halts after error, no reflection call, or fallback missing. |
| X3 | "Merge 'Battery Cost Analysis' with the newest allowed web article on solid-state batteries and output a critic-approved report." | search_documents → extract_section → google_search (whitelisted) → extract_page_content → synthesize_content → create_detailed_report(report_style="executive") → Critic.check_quality. | Report cites both sources, QC passes or documents re-plan, routing spans File+Browser+Writing+Critic. | Disallowed domain, missing reference, QC ignored, or replan loop absent. |
| X4 | "Draft a tool-by-tool plan for capturing a Discord digest, have the PlanValidator approve it, then execute and submit the summary for critic verification." | Planner outlines steps → Critic.validate_plan → ensure_discord_session → discord_read_channel_messages → create_meeting_notes → Critic.verify_output. | Plan approval stored, digest includes timestamps/actions, critic verdict returned. | Invalid plan executed, digest missing, or critic not run. |

## Edge Cases & Ambiguity

| ID | Test Query | Expected Path | Success Criteria | Failure Indicators |
|----|------------|---------------|------------------|--------------------|
| E1 | "Email that draft to marketing ASAP." | Planner detects missing context → asks clarifying question (no tool execution). | Assistant requests file name/path or recent context, state remains in planning. | Random file guessed, search runs blindly, or email sent without confirmation. |
| E2 | "Plan a trip with two food stops." | Planner requests origin/destination before invoking maps tools. | Clarification requested, no `plan_trip_with_stops` call until parameters provided. | Agent fabricates locations, runs tool with guesses, or errors silently. |
| E3 | "Scrape https://random-news.ru for today's headlines." | Planner checks `browser.allowed_domains` → refuses with explanation. | Response cites whitelist and offers allowed alternatives. | google_search/navigate_to_url attempted on blocked domain. |
| E4 | "Use the translate_document tool to convert the Tesla memo to Spanish." | Planner/validator notes tool missing → respond with `complexity="impossible"`. | Clear refusal referencing tool catalog, no executor activity. | Tool hallucinated or substitute used without confirmation. |

## High-Complexity Tasks

| ID | Test Query | Expected Path | Success Criteria | Failure Indicators |
|----|------------|---------------|------------------|--------------------|
| H1 | "Produce a board-ready update on Tesla's Q2 performance..." | search_documents → extract_section → google_search (allowed finance site) → navigate_to_url → extract_page_content → synthesize_content → create_slide_deck_content(num_slides=6) → create_keynote → compose_email(send=false) → Critic.check_quality. | Both sources cited, slide count ≈6, email draft references attachments, QC passes tone/style. | Web source missing, disallowed domain, slide count off, or email lacks attachment info. |
| H2 | "Aggregate sentiment from Discord #product-feedback, r/electricvehicles, and the product_watch Twitter list over the last 12 hours..." | ensure_discord_session → discord_read_channel_messages(window=12h) → scan_subreddit_posts → summarize_list_activity(lookback_hours=12) → synthesize_content(comparative) → create_detailed_report(report_style="executive") → Critic.verify_output. | Report compares three channels with risk rating, critic confirms coverage. | Any source skipped, timestamps ignored, or critic absent. |
| H3 | "Run financial due diligence on NVIDIA..." | search_google_finance_stock → extract_google_finance_data → capture_google_finance_chart → get_stock_history → synthesize_content → create_detailed_report → ReportAgent.create_stock_report(optional) → Critic.check_quality. | Data + chart paths stored, report references Google Finance + yfinance metrics, QC passes. | Chart missing, yfinance not called, or QC skipped. |
| H4 | "Act as my travel concierge for a 4-day Bay Area → Monterey → Big Sur → Santa Barbara loop..." | plan_trip_with_stops per leg → open_maps_with_route → send_imessage(per-day link) → create_pages_doc(itinerary) → compose_email(attach doc) → Critic.verify_output. | Each day yields maps_url + iMessage status, itinerary doc includes schedule, email prepared. | Routes not opened, messages absent, or critic omitted. |

## Failure-Mode & Recovery

| ID | Test Query | Expected Path | Success Criteria | Failure Indicators |
|----|------------|---------------|------------------|--------------------|
| F1 | "Email the PDF 'market_update_final.pdf' to finance even if the file isn't on disk anymore—figure it out." | compose_email (fails missing file) → Critic.reflect_on_failure → search_documents/organize_files to locate replacement → compose_email retry → Critic.verify_output. | Failure logged, reflection suggests recovery, email only sent once attachment resolved or impossibility stated. | Email sent with broken attachment, no reflection step, or no retry. |
| F2 | "Plan a cross-country trip from NYC to LA with 12 fuel and 12 food stops." | plan_trip_with_stops (exceeds limit) → error surfaced → reflect_on_failure → prompt user to reduce stops or auto-trim before rerun. | Constraint violation explained, follow-up respects max stop cap. | Agent fabricates plan ignoring limits or crashes without guidance. |
| F3 | "Create a stock report on SpaceX." | create_stock_report(company="SpaceX") → PrivateCompany error → reflect_on_failure → suggest alternative/public peer → Critic.verify_output of explanation. | Clear message SpaceX is private, corrective action proposed, no stuck state. | Fake ticker invented, endless loop, or silent failure. |
| F4 | "Capture the latest updates from Discord #launch-war-room even if the session is expired; recover and continue." | ensure_discord_session (fails) → reflect_on_failure with remediation → ensure_discord_session retry → discord_read_channel_messages → capture_screenshot → Critic.check_quality. | Session recovery logged, final data delivered, critic confirms. | Failure not detected, no retry, or digest missing after recovery. |

## Winning Scenarios

| ID | Test Query | Expected Path | Success Criteria | Failure Indicators |
|----|------------|---------------|------------------|--------------------|
| W1 | "From the 'EV Strategy deck', output a zipped artifact containing the PDF, an extracted summary, and a fresh Keynote." | search_documents → extract_section → create_keynote → create_zip_archive(files=[pdf, summary, keynote]) → Critic.verify_output. | ZIP contains all assets, summary references deck, verification passes. | ZIP missing items, wrong files zipped, or critic skipped. |
| W2 | "Research 'Palantir defense contracts' on allowed sites, write a 2-page Pages brief with inline citations, and email it for approval after QC." | google_search → navigate_to_url → extract_page_content → synthesize_content → create_detailed_report → create_pages_doc → compose_email(send=false) → Critic.check_quality. | Pages doc ≈2 pages with citations, email references doc, QC confirms completeness. | Disallowed source, doc length off, or QC absent. |
| W3 | "Generate a combined Discord + Twitter status update and post it into #executive-briefings." | summarize_list_activity → ensure_discord_session → discord_detect_unread_channels(optional) → synthesize_content → discord_send_message(channel="#executive-briefings") → Critic.verify_output. | Message references both channels, Discord send confirms, critic signs off. | Single source only, post fails, or verification missing. |
| W4 | "Gather Google Finance data for Microsoft, produce a PDF stock report plus attach the chart screenshot, and email both." | search_google_finance_stock → extract_google_finance_data → capture_google_finance_chart → create_stock_report_from_google_finance("Microsoft") → compose_email(attach report + chart) → Critic.check_quality. | Report + screenshot paths attached, email draft references both, QC confirms. | Attachments missing, chart not captured, or email sent without summary/QC. |
