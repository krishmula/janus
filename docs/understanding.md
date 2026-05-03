# What I'm understanding about Janus (Ongoing)

3 May '26

1. We're building a InteractAPI first. So, this takes natural lang as the input, and via a translation engine, turns it into safe, digestable commands for the agent.
2. Then, this is taken as input by the agent, which is basically the same as an LLM.
3. The agent then executes the command, i.e. it considers these commands/instructions, and uses Playwright to implenent it.
4. For example, if the command is "Go to google.com and search for 'best restaurants in NYC'", the agent will use Playwright to open a browser, navigate to google.com, and perform the search.
5. Playwright usually uses a headless browser, so, it doesn't open a full browser, but a lightweight version that can be controlled programmatically.
6. But, one of the complexities of this challenge is to use our own browser, or the user's browser, not a headless one. This is complex, as controlling a user's browser is significantly more difficult.
7. Then, we have to get the result of the actions happening in the browser.
8. The actions that will happen on the browswer that we will be interested in will be part of our initial limited Action Vocab. (This will keep expanding, for now it has "goto", "click", "type", "scroll", "press", "wait", "extract_text", "ask_user", "screenshot" etc.)
9. So, now, we have to get the results of these actions, which we have to also do through an API, which will be the ExtractAPI.
10. The ExtractAPI will be responsible for retrieving and parsing the results of the structured data from the web pages that the browser has loaded.
11. So, right now, the thing is, we just go to the web page, extract the text, or just take a screenshot. I'm not building anything more complex (no time, maybe later).
