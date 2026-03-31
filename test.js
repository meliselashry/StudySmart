//const { chromium } = require('playwright');

//(async () => {
//  const browser = await chromium.launch({ headless: false });
  //const page = await browser.newPage();

  //await page.goto('https://quizlet.com/create-set');

  //await page.waitForTimeout(5000);

  //await browser.close();
//})();

def send_vocab_to_quizlet(vocab_text: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=250)

        if os.path.exists(QUIZLET_STORAGE_STATE):
            context = browser.new_context(storage_state=QUIZLET_STORAGE_STATE)
        else:
            context = browser.new_context()

        page = context.new_page()
        page.goto("https://www.google.com/", wait_until="load")
        page.wait_for_timeout(5000)

        # First-time login support
        if "login" in page.url.lower():
            raise Exception(
                "Quizlet needs you to log in first in the Playwright browser. "
                "After logging in once, run the button again."
            )

        # You are already on the create-set page, so skip flashcards click

        # Click the first Import button
        import_buttons = page.get_by_role("button", name=re.compile(r"import", re.I))
        if import_buttons.count() == 0:
            raise Exception("Could not find the Quizlet import button.")

        import_buttons.first.click()
        page.wait_for_timeout(2000)

        # Fill the import text box
        textarea = page.locator("textarea").first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.fill(vocab_text)

        page.wait_for_timeout(1000)

        # Click the final Import button in the popup
        import_buttons = page.get_by_role("button", name=re.compile(r"^import$", re.I))
        if import_buttons.count() == 0:
            raise Exception("Could not find the final import button.")

        import_buttons.last.click()

        context.storage_state(path=QUIZLET_STORAGE_STATE)
