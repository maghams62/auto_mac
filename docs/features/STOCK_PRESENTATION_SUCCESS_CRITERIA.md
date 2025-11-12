# Stock Presentation Success Criteria

This document defines the success criteria for the enhanced stock presentation creation feature.

## Overview

The stock presentation feature creates comprehensive, well-researched 5-slide presentations about stocks using:
- Real-time stock data from yfinance
- Comprehensive web searches via DuckDuckGo
- Intelligent query rewriting and result parsing
- AI-powered slide planning and content synthesis

## Success Criteria

### 1. Presentation Structure

#### ✅ Slide Count
- **Requirement**: Presentation must have exactly 5 content slides (plus title slide)
- **Verification**: Count slides in created Keynote file
- **Acceptance**: 5 slides present

#### ✅ Slide Structure
- **Slide 1: Stock Price Overview**
  - Current price with currency symbol
  - Price change (both dollar amount and percentage)
  - Previous close price
  - Data date (when the price data is from)
  
- **Slide 2: Performance Metrics**
  - 52-week high and low range
  - Market capitalization
  - Average trading volume
  
- **Slide 3: Company Analysis**
  - Business overview (concise)
  - Key products/services
  - Market position/strength
  
- **Slide 4: Market Analysis**
  - Recent news highlights
  - Market trends
  - Analyst insights
  
- **Slide 5: Conclusion & Outlook**
  - Key strengths
  - Key considerations/risks
  - Investment outlook summary

#### ✅ Bullet Points
- Each slide must have 3-4 bullet points
- Each bullet point should be MAX 7 words (shorter is better)
- Bullet points must be concise and data-driven

### 2. Data Accuracy

#### ✅ Stock Price Data
- Current price must be accurate (from yfinance)
- Price change calculation must be correct
- Previous close must be accurate
- Data date must be included and accurate

#### ✅ Financial Metrics
- 52-week range must be accurate
- Market cap must be accurate
- Volume data must be accurate
- P/E ratio and other metrics must be accurate (if available)

#### ✅ Data Freshness
- Data should be recent (within 7 days preferred)
- If data is older than 3 days, disclaimer should be included
- Data date must be clearly displayed

### 3. Search Quality

#### ✅ Comprehensive Searches
- Must perform 5 comprehensive web searches:
  1. Stock price and current performance
  2. Company overview and business model
  3. Recent news and developments
  4. Market analysis and trends
  5. Financial metrics and valuation

#### ✅ Query Rewriting
- Search queries must be intelligently rewritten for better results
- Rewritten queries should be semantic and comprehensive
- Example: "NVIDIA stock" → "NVIDIA NVDA stock price performance analysis 2024"

#### ✅ Result Parsing
- Search results must be intelligently parsed
- Key information must be extracted and organized
- Parsed information must be incorporated into slides

### 4. Planning Stage

#### ✅ Slide Planning
- Must create explicit slide structure plan before generating content
- Plan must define what information goes in each slide
- Plan must specify key points to highlight
- Plan must organize slides logically

#### ✅ Plan Execution
- Final slides must follow the planned structure
- Plan must be used to guide content generation
- Plan should be logged/returned for verification

### 5. Content Quality

#### ✅ Data-Driven Content
- All content must be based on actual data
- Specific numbers and figures must be used
- No generic or vague statements

#### ✅ Conciseness
- Bullet points must be concise (max 7 words)
- Content must be focused and relevant
- No unnecessary information

#### ✅ Professional Tone
- Content must be professional and appropriate for financial presentation
- Language must be clear and accessible
- Technical terms should be used appropriately

### 6. Email Functionality (When Requested)

#### ✅ Email Creation
- Email must be created with proper subject line
- Subject: "{Company Name} ({Ticker}) Stock Analysis Report"

#### ✅ Email Body
- Email body must include:
  - Company name and ticker
  - Current price and change
  - Data date
  - Summary of presentation contents
  - Research sources information

#### ✅ Attachment Handling (CRITICAL!)
- **File Existence Verification**: Presentation file path must be verified to exist before attaching
- **Absolute Paths**: File paths must be converted to absolute paths before attaching
- **File Validation**: Must verify file is:
  - A file (not a directory)
  - Readable (has read permissions)
  - Actually exists on the filesystem
- **Error Handling**: If file not found or invalid, must return clear error message
- **Logging**: Attachment validation status must be logged before sending
- **Success Criteria**: Email with "email a slideshow" MUST have the presentation file attached, or return error

#### ✅ Email Sending
- Email must be sent successfully (if send=True)
- Email status must be returned
- Errors must be handled gracefully

### 7. Error Handling

#### ✅ Ticker Resolution
- Must handle both company names and ticker symbols
- Must provide helpful error messages if ticker not found
- Must suggest using ticker symbol if lookup fails

#### ✅ Search Failures
- Must handle search failures gracefully
- Must fall back to available data if searches fail
- Must continue with available information

#### ✅ Presentation Creation Failures
- Must return clear error messages
- Must indicate if retry is possible
- Must log errors for debugging

## Testing Criteria

### Unit Tests
- Test query rewriting functionality
- Test search result parsing
- Test slide structure planning
- Test email composition

### Integration Tests
- Test full presentation creation workflow
- Test with various company names and tickers
- Test email functionality

### Browser Automation Tests
- Test presentation creation via UI
- Test email sending via UI
- Verify slide structure in created presentation
- Verify email content and attachments

## Example Success Scenario

**Input**: "Fetch the stock price of NVIDIA and create a presentation"

**Expected Output**:
1. ✅ Presentation created with 5 slides
2. ✅ Slide 1 contains current NVIDIA stock price, change, date
3. ✅ Slides 2-5 contain relevant analysis
4. ✅ All data is accurate and current
5. ✅ Content is concise and data-driven
6. ✅ Search results are intelligently incorporated

**Input**: "Fetch the stock price of NVIDIA and create a presentation and email it to me"

**Expected Output**:
1. ✅ All above criteria met
2. ✅ Email sent successfully
3. ✅ Email contains proper subject and body
4. ✅ Presentation attached to email
5. ✅ Email recipient is correct

## Non-Functional Requirements

### Performance
- Presentation creation should complete within reasonable time (< 2 minutes)
- Search queries should complete within reasonable time (< 30 seconds total)

### Reliability
- Feature should work consistently across different stocks
- Should handle edge cases gracefully
- Should provide helpful error messages

### Maintainability
- Code should be well-documented
- Logging should be comprehensive
- Error messages should be clear

## Verification Checklist

When testing the feature, verify:

- [ ] Presentation has exactly 5 slides
- [ ] Slide 1 contains stock price information prominently
- [ ] All slides have 3-4 bullet points
- [ ] Bullet points are concise (max 7 words)
- [ ] Stock price data is accurate
- [ ] Financial metrics are accurate
- [ ] Data date is included
- [ ] 5 comprehensive searches were performed
- [ ] Search queries were rewritten intelligently
- [ ] Search results were parsed intelligently
- [ ] Slide plan was created before content generation
- [ ] Content is data-driven with specific numbers
- [ ] Content is professional and appropriate
- [ ] Email functionality works (if requested)
- [ ] Email has proper subject and body
- [ ] Presentation is attached to email
- [ ] Errors are handled gracefully

## Success Metrics

- **Accuracy**: 95%+ of stock data should be accurate
- **Completeness**: 100% of presentations should have 5 slides
- **Search Quality**: 80%+ of searches should return relevant results
- **Email Success**: 95%+ of emails should send successfully
- **User Satisfaction**: Presentations should be useful and informative

