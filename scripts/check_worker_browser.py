"""Check the shipped non-root browser runtime without external network or credentials."""
import asyncio
from playwright.async_api import async_playwright


async def verify():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content('<html><body><h1>Worker browser ready</h1></body></html>')
            if await page.locator('h1').inner_text() != 'Worker browser ready':
                raise RuntimeError('worker_browser_not_ready')
        finally:
            await browser.close()
    print('worker_browser_ready')


if __name__ == '__main__':
    asyncio.run(verify())
