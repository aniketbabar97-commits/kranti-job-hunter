@echo off
rem helper\browser.bat <id> <mcp-config-file>
rem Plain Playwright: it starts and drives its own Chrome window (fastest, as in the first runs). Own profile per
rem worker, so logins/cookies survive between nights and her normal Chrome / YouTube is never touched.
> %2 echo {"mcpServers":{"playwright":{"command":"cmd","args":["/c","npx","@playwright/mcp@latest","--browser","chrome","--user-data-dir","out\\pw-profile-%1"]}}}
echo [%date% %time%] browser %1: Playwright-managed Chrome >> out\nightly_diag.log
