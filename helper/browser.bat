@echo off
rem helper\browser.bat <port> <mcp-config-file>
rem Starts a SEPARATE Chrome (own profile, never her normal Chrome/YouTube window) with a debugging port and writes the
rem Playwright MCP config for it. If that Chrome does not answer, falls back to a browser that Playwright starts itself.
set PORT=%1
set CFG=%2
start "" chrome --remote-debugging-port=%PORT% --user-data-dir="%CD%\out\chrome-apply-%PORT%" --no-first-run about:blank
set OK=
for /L %%t in (1,1,10) do if not defined OK (
  powershell -NoProfile -Command "try{(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%PORT%/json/version -TimeoutSec 2)|Out-Null;exit 0}catch{exit 1}" && set OK=1
  if not defined OK timeout /t 2 >nul
)
if defined OK (
  > %CFG% echo {"mcpServers":{"playwright":{"command":"cmd","args":["/c","npx","@playwright/mcp@latest","--cdp-endpoint","http://127.0.0.1:%PORT%"]}}}
  echo [%date% %time%] browser %PORT%: own Chrome window OK >> out\nightly_diag.log
) else (
  > %CFG% echo {"mcpServers":{"playwright":{"command":"cmd","args":["/c","npx","@playwright/mcp@latest","--browser","chrome","--user-data-dir","out\\pw-profile-%PORT%"]}}}
  echo [%date% %time%] browser %PORT%: debugging port not reachable, Playwright starts its own Chrome >> out\nightly_diag.log
)
