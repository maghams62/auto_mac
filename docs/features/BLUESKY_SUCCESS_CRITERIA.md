# Bluesky Tweet Success Criteria

This document defines the success criteria for Bluesky tweet summarization and retrieval features.

## Overview

The Bluesky agent provides functionality to:
- Search public Bluesky posts
- Get posts from specific authors
- Summarize posts with AI
- Handle "last N tweets" queries accurately

## Success Criteria

### 1. Tweet Count Accuracy (CRITICAL!)

#### ✅ Exact Count Matching
- **Requirement**: When user requests "last N tweets", system MUST return exactly N tweets
- **Example**: "Summarize the last 5 tweets" → Must return exactly 5 tweets
- **Verification**: Check `count` field in response matches `requested_count`
- **Acceptance**: `count == requested_count` (or error if insufficient tweets available)

#### ✅ Count Validation
- System must validate that returned count matches requested count
- If fewer tweets available than requested, must log warning
- Response must include both `count` and `requested_count` fields

### 2. Chronological Order

#### ✅ Most Recent First
- **Requirement**: Tweets must be returned in chronological order (most recent first)
- **Verification**: Check `created_at` timestamps are descending
- **Acceptance**: Each tweet's timestamp >= next tweet's timestamp

#### ✅ Order Validation
- System must validate chronological order
- Must log warning if order is incorrect
- Sorting must be by `created_at` timestamp (descending)

### 3. Correct User/Feed

#### ✅ Author Accuracy
- **Requirement**: When requesting "my tweets" or specific author, all tweets must be from that author
- **Verification**: Check `author_handle` matches requested user
- **Acceptance**: All returned tweets have matching `author_handle`

#### ✅ Feed Source
- For "last N tweets" queries, must use author feed (not search)
- Must disable time filtering for "last N tweets" queries
- Must use authenticated user's feed when no actor specified

### 4. Content Quality

#### ✅ No Random/Unrelated Tweets
- **Requirement**: Tweets must be relevant and from correct source
- **Verification**: Check tweet content and author match query intent
- **Acceptance**: No unrelated or random tweets in results

#### ✅ Tweet Structure
- Each tweet must have:
  - `text`: Tweet content
  - `author_handle`: Author's Bluesky handle
  - `author_name`: Author's display name
  - `created_at`: Timestamp (ISO format)
  - `url`: Public Bluesky URL
  - Engagement metrics (likes, reposts, replies, quotes)

### 5. Query Pattern Recognition

#### ✅ "Last N Tweets" Detection
- System must recognize patterns:
  - "last N tweets" → Use author feed, return exactly N tweets
  - "my tweets" → Use authenticated user's feed
  - "recent tweets" → Use author feed
- Must extract number from query (e.g., "last 5 tweets" → 5)

#### ✅ Time Filtering
- For "last N tweets", must disable time filtering
- For other queries, may apply time filtering based on `lookback_hours`

### 6. Summarization Quality

#### ✅ Summary Accuracy
- Summary must accurately reflect tweet content
- Must reference tweet numbers in brackets (e.g., [1], [2])
- Must include key takeaways and insights

#### ✅ Summary Structure
- Short paragraph overview
- Bullet list of key takeaways
- Links section with URLs

### 7. Error Handling

#### ✅ Invalid Queries
- Empty queries must return error
- Invalid actor handles must be handled gracefully
- API errors must be caught and returned with clear messages

#### ✅ Insufficient Tweets
- If fewer tweets available than requested, must:
  - Return available tweets
  - Log warning about count mismatch
  - Include `requested_count` vs `count` in response

## Testing Criteria

### Unit Tests
- Test exact count matching for "last N tweets"
- Test chronological order validation
- Test author accuracy
- Test query pattern recognition

### Integration Tests
- Test full workflow: query → fetch → summarize
- Test with various query patterns
- Test error handling

### Browser Automation Tests
- Test "last 5 tweets" returns exactly 5
- Test tweets are in chronological order
- Test tweets are from correct user
- Test summary quality

## Example Success Scenarios

### Scenario 1: "Summarize the last 5 tweets"

**Input**: "Summarize the last 5 tweets"

**Expected Output**:
1. ✅ Exactly 5 tweets returned (`count: 5`, `requested_count: 5`)
2. ✅ Tweets in chronological order (most recent first)
3. ✅ All tweets from authenticated user
4. ✅ Summary includes references to tweets [1]-[5]
5. ✅ Summary includes key insights and links

**Verification**:
```python
result = summarize_bluesky_posts(query="last 5 tweets")
assert result["count"] == 5
assert result["requested_count"] == 5
assert len(result["items"]) == 5
# Check chronological order
timestamps = [item["created_at"] for item in result["items"]]
assert timestamps == sorted(timestamps, reverse=True)
```

### Scenario 2: "Get my recent tweets and email them"

**Input**: "Get my recent tweets and email them"

**Expected Output**:
1. ✅ Tweets fetched from authenticated user's feed
2. ✅ Tweets formatted in email body
3. ✅ Email sent successfully
4. ✅ Email contains tweet content

## Non-Functional Requirements

### Performance
- Tweet fetching should complete within reasonable time (< 10 seconds)
- Summarization should complete within reasonable time (< 30 seconds)

### Reliability
- Feature should work consistently across different users
- Should handle API rate limits gracefully
- Should provide helpful error messages

### Maintainability
- Code should be well-documented
- Logging should be comprehensive
- Error messages should be clear

## Verification Checklist

When testing the feature, verify:

- [ ] "Last N tweets" returns exactly N tweets
- [ ] Tweets are in chronological order (most recent first)
- [ ] All tweets are from correct user
- [ ] No random or unrelated tweets
- [ ] Query patterns are recognized correctly
- [ ] Time filtering is disabled for "last N tweets"
- [ ] Summary accurately reflects tweet content
- [ ] Summary includes tweet references [1], [2], etc.
- [ ] Errors are handled gracefully
- [ ] Count validation works correctly

## Success Metrics

- **Count Accuracy**: 100% of "last N tweets" queries should return exactly N tweets (or error if insufficient)
- **Chronological Order**: 100% of tweet lists should be in correct order
- **Author Accuracy**: 100% of tweets should be from requested author
- **Query Recognition**: 95%+ of query patterns should be recognized correctly
- **Summary Quality**: Summaries should be accurate and useful

## Common Mistakes to Avoid

❌ **Returning wrong count**: "Last 5 tweets" returns 3 or 7 tweets
❌ **Wrong order**: Tweets not in chronological order
❌ **Wrong user**: Tweets from different user than requested
❌ **Random tweets**: Including unrelated tweets in results
❌ **Missing validation**: Not checking count or order
❌ **Time filtering**: Applying time filter to "last N tweets" queries

## Implementation Notes

- Use `get_author_feed` for "last N tweets" queries (not `search_posts`)
- Disable time filtering for "last N tweets" queries
- Sort by `created_at` descending (most recent first)
- Validate count and order before returning results
- Include `requested_count` and `count` in response for verification

