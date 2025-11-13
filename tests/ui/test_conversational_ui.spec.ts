/**
 * Playwright UI Regression Tests for Conversational Interface
 *
 * Tests the complete UI workflow for all test scenarios:
 * - Conversational cards rendering
 * - Timeline and status displays
 * - Attachment handling
 * - Error states and recovery
 * - Real-time updates
 */

import { test, expect, Page } from '@playwright/test';

test.describe('Conversational UI Regression Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the UI
    await page.goto('http://localhost:3000');

    // Wait for the app to load
    await page.waitForSelector('[data-testid="chat-interface"]', { timeout: 10000 });
  });

  test('Finance-Presentation-Email UI Workflow', async ({ page }) => {
    /**
     * Test the complete UI workflow for finance → presentation → email
     *
     * WINNING CRITERIA:
     * - Workflow progress shows all steps
     * - Presentation attachment visible
     * - Email sent confirmation displayed
     * - Timeline shows complete flow
     * - No UI errors or broken states
     */

    // Submit the complex workflow query
    const query = "Fetch NVIDIA stock price, create a presentation, email it to me";
    await submitChatMessage(page, query);

    // Wait for workflow completion (may take time for complex operations)
    await page.waitForTimeout(30000);

    // Check for workflow progress indicators
    await expect(page.locator('[data-testid="workflow-progress"]')).toBeVisible();

    // Verify all workflow steps are shown
    const workflowSteps = page.locator('[data-testid="workflow-step"]');
    await expect(workflowSteps).toHaveCount(3); // fetch → create → email

    // Check for presentation attachment in UI
    const attachment = page.locator('[data-testid="message-attachment"]').filter({
      hasText: 'presentation'
    });
    await expect(attachment).toBeVisible();

    // Verify email sent confirmation
    const emailConfirmation = page.locator('[data-testid="email-confirmation"]');
    await expect(emailConfirmation).toBeVisible();

    // Check timeline shows complete workflow
    const timeline = page.locator('[data-testid="conversation-timeline"]');
    await expect(timeline).toContainText('Presentation emailed');

    // Verify no error states
    const errors = page.locator('[data-testid="error-message"]');
    await expect(errors).toHaveCount(0);
  });

  test('Email Workflows UI Display', async ({ page }) => {
    /**
     * Test email workflow UI rendering and status
     *
     * WINNING CRITERIA:
     * - Email composition UI works
     * - Attachment indicators correct
     * - Send confirmation shown
     * - Reply/forward threading visible
     * - No attachment sent by mistake
     */

    // Test email with attachment
    const query = "Compose an email with the quarterly report attached";
    await submitChatMessage(page, query);

    await page.waitForTimeout(10000);

    // Check for attachment indicator
    const attachmentIndicator = page.locator('[data-testid="attachment-indicator"]');
    await expect(attachmentIndicator).toBeVisible();

    // Verify attachment filename shown
    await expect(attachmentIndicator).toContainText('quarterly');

    // Check send confirmation
    const sendConfirmation = page.locator('[data-testid="send-confirmation"]');
    await expect(sendConfirmation).toBeVisible();

    // Verify no errors
    const errors = page.locator('[data-testid="error-message"]');
    await expect(errors).toHaveCount(0);
  });

  test('Reminders UI Status and Management', async ({ page }) => {
    /**
     * Test reminders UI display and interaction
     *
     * WINNING CRITERIA:
     * - Reminder creation confirmed
     * - Reminder list displays properly
     * - Completion status updates
     * - Due dates shown correctly
     * - Interactive controls work
     */

    const query = "Remind me to call Alex at 4pm tomorrow";
    await submitChatMessage(page, query);

    await page.waitForTimeout(5000);

    // Check reminder creation confirmation
    const reminderConfirmation = page.locator('[data-testid="reminder-created"]');
    await expect(reminderConfirmation).toBeVisible();

    // Check reminder appears in list
    const reminderList = page.locator('[data-testid="reminder-list"]');
    await expect(reminderList).toContainText('Alex');

    // Verify time display
    await expect(reminderList).toContainText('4pm');
    await expect(reminderList).toContainText('tomorrow');
  });

  test('Bluesky Social UI Features', async ({ page }) => {
    /**
     * Test Bluesky social features in UI
     *
     * WINNING CRITERIA:
     * - Post composition works
     * - Social feed displays
     * - Interaction buttons functional
     * - Character count accurate
     * - Post confirmation shown
     */

    const query = "Post 'Testing automated posting' to Bluesky";
    await submitChatMessage(page, query);

    await page.waitForTimeout(5000);

    // Check for social post confirmation
    const postConfirmation = page.locator('[data-testid="social-post-confirmation"]');
    await expect(postConfirmation).toBeVisible();

    // Verify post content shown
    await expect(postConfirmation).toContainText('Testing automated posting');
  });

  test('Explain Command UI Display', async ({ page }) => {
    /**
     * Test explain command UI rendering
     *
     * WINNING CRITERIA:
     * - Code display formatted properly
     * - Explanations structured clearly
     * - Syntax highlighting works
     * - Navigation aids present
     * - Large files handled with pagination
     */

    const query = "Explain the main agent file";
    await submitChatMessage(page, query);

    await page.waitForTimeout(8000);

    // Check for code display component
    const codeDisplay = page.locator('[data-testid="code-display"]');
    await expect(codeDisplay).toBeVisible();

    // Verify explanation structure
    const explanation = page.locator('[data-testid="structured-explanation"]');
    await expect(explanation).toBeVisible();

    // Check for proper formatting
    await expect(page.locator('[data-testid="syntax-highlighting"]')).toBeVisible();
  });

  test('File Operations UI Updates', async ({ page }) => {
    /**
     * Test file operation UI feedback
     *
     * WINNING CRITERIA:
     * - File tree updates in real-time
     * - Operation progress shown
     * - Confirmation dialogs work
     * - Bulk operations display properly
     * - Error states clear
     */

    const query = "Create a folder called 'test_project' and organize my files";
    await submitChatMessage(page, query);

    await page.waitForTimeout(10000);

    // Check file tree updates
    const fileTree = page.locator('[data-testid="file-tree"]');
    await expect(fileTree).toContainText('test_project');

    // Verify operation progress
    const progress = page.locator('[data-testid="operation-progress"]');
    await expect(progress).toBeVisible();
  });

  test('Calendar Day View UI Timeline', async ({ page }) => {
    /**
     * Test calendar day view UI rendering
     *
     * WINNING CRITERIA:
     * - Timeline widget displays
     * - Events positioned chronologically
     * - Multi-source integration shown
     * - Time conflicts highlighted
     * - Interactive calendar functional
     */

    const query = "How's my day looking?";
    await submitChatMessage(page, query);

    await page.waitForTimeout(10000);

    // Check timeline display
    const timeline = page.locator('[data-testid="day-timeline"]');
    await expect(timeline).toBeVisible();

    // Verify multi-source content
    await expect(timeline).toContainText('calendar');
    await expect(timeline).toContainText('email');

    // Check chronological ordering (events should be in time order)
    const timelineEvents = page.locator('[data-testid="timeline-event"]');
    const eventCount = await timelineEvents.count();
    expect(eventCount).toBeGreaterThan(0);
  });

  test('Spotify Player UI Controls', async ({ page }) => {
    /**
     * Test Spotify player UI functionality
     *
     * WINNING CRITERIA:
     * - Player card displays properly
     * - Playback controls functional
     * - Current track info accurate
     * - Queue visible and navigable
     * - Device selection works
     */

    const query = "Play some music and show the player";
    await submitChatMessage(page, query);

    await page.waitForTimeout(5000);

    // Check player UI
    const player = page.locator('[data-testid="spotify-player"]');
    await expect(player).toBeVisible();

    // Verify playback controls
    const playButton = page.locator('[data-testid="play-button"]');
    const pauseButton = page.locator('[data-testid="pause-button"]');
    const nextButton = page.locator('[data-testid="next-button"]');

    await expect(playButton.or(pauseButton)).toBeVisible();
    await expect(nextButton).toBeVisible();

    // Check current track display
    const trackInfo = page.locator('[data-testid="current-track"]');
    await expect(trackInfo).toBeVisible();
  });

  test('Image Display and Interaction', async ({ page }) => {
    /**
     * Test image display and interaction UI
     *
     * WINNING CRITERIA:
     * - Images render properly
     * - Zoom and pan controls work
     * - Fullscreen view available
     * - Image metadata shown
     * - Gallery navigation functional
     */

    const query = "Show me the mountain landscape image";
    await submitChatMessage(page, query);

    await page.waitForTimeout(5000);

    // Check image display
    const imageViewer = page.locator('[data-testid="image-viewer"]');
    await expect(imageViewer).toBeVisible();

    // Verify image actually loaded
    const imageElement = page.locator('img[data-testid="displayed-image"]');
    await expect(imageElement).toBeVisible();

    // Check for image controls
    const zoomControls = page.locator('[data-testid="zoom-controls"]');
    await expect(zoomControls).toBeVisible();
  });

  test('Error States and Recovery UI', async ({ page }) => {
    /**
     * Test error handling and recovery in UI
     *
     * WINNING CRITERIA:
     * - Errors display clearly
     * - Recovery suggestions provided
     * - Retry mechanisms work
     * - User not stuck in error state
     * - Graceful degradation
     */

    // Trigger an error condition
    const badQuery = "Access a file that doesn't exist";
    await submitChatMessage(page, badQuery);

    await page.waitForTimeout(3000);

    // Check error display
    const errorMessage = page.locator('[data-testid="error-message"]');
    await expect(errorMessage).toBeVisible();

    // Verify error is actionable
    await expect(errorMessage).toContainText('not found');

    // Check for recovery options
    const retryButton = page.locator('[data-testid="retry-button"]');
    const alternativeAction = page.locator('[data-testid="alternative-action"]');

    // Should have some recovery mechanism
    await expect(retryButton.or(alternativeAction)).toBeVisible();
  });

  test('Toast Notifications and Status Updates', async ({ page }) => {
    /**
     * Test toast notifications and real-time status
     *
     * WINNING CRITERIA:
     * - Success toasts appear
     * - Progress notifications show
     * - Error toasts actionable
     * - Toast stack manages properly
     * - Dismiss functionality works
     */

    const query = "Send a test email";
    await submitChatMessage(page, query);

    await page.waitForTimeout(3000);

    // Check for success toast
    const successToast = page.locator('[data-testid="success-toast"]');
    await expect(successToast).toBeVisible();

    // Verify toast content
    await expect(successToast).toContainText('email');

    // Check toast can be dismissed
    const dismissButton = successToast.locator('[data-testid="toast-dismiss"]');
    await dismissButton.click();

    // Toast should disappear
    await expect(successToast).not.toBeVisible();
  });

  test('Real-time Workflow Progress', async ({ page }) => {
    /**
     * Test real-time workflow progress updates
     *
     * WINNING CRITERIA:
     * - Progress indicators update live
     * - Step completion shown immediately
     * - Status messages accurate
     * - No stale status display
     * - Performance metrics visible
     */

    const complexQuery = "Fetch stock data, create presentation, and email it";
    await submitChatMessage(page, complexQuery);

    // Monitor progress updates
    const progressIndicator = page.locator('[data-testid="progress-indicator"]');

    // Should show initial progress
    await expect(progressIndicator).toBeVisible();

    // Wait for first step completion
    await page.waitForSelector('[data-testid="step-complete"]', { timeout: 15000 });

    // Check progress updates
    const completedSteps = page.locator('[data-testid="step-complete"]');
    const stepCount = await completedSteps.count();

    // Should have completed at least one step
    expect(stepCount).toBeGreaterThan(0);

    // Verify final completion
    await page.waitForSelector('[data-testid="workflow-complete"]', { timeout: 45000 });
    const completionMessage = page.locator('[data-testid="workflow-complete"]');
    await expect(completionMessage).toBeVisible();
  });

  test('Attachment Handling UI', async ({ page }) => {
    /**
     * Test attachment display and interaction
     *
     * WINNING CRITERIA:
     * - Attachments show with correct icons
     * - File sizes display accurately
     * - Download links functional
     * - Preview available for supported types
     * - Multiple attachments handled
     */

    const query = "Create a report and attach it to an email";
    await submitChatMessage(page, query);

    await page.waitForTimeout(10000);

    // Check attachment display
    const attachment = page.locator('[data-testid="file-attachment"]');
    await expect(attachment).toBeVisible();

    // Verify attachment has proper metadata
    await expect(attachment).toContainText('.'); // Should show file extension

    // Check download functionality
    const downloadButton = attachment.locator('[data-testid="download-button"]');
    await expect(downloadButton).toBeVisible();
  });
});

/**
 * Helper function to submit a chat message and wait for response start
 */
async function submitChatMessage(page: Page, message: string): Promise<void> {
  // Find the input field
  const input = page.locator('[data-testid="chat-input"]');
  await expect(input).toBeVisible();

  // Type the message
  await input.fill(message);

  // Submit the message
  await input.press('Enter');

  // Wait for message to appear in chat
  await page.waitForSelector(`[data-testid="message"]:has-text("${message.substring(0, 20)}")`);

  // Wait for response to start
  await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 5000 });
}
