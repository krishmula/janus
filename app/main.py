from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpcore import request

app = FastAPI()


@app.post("/api/interact")
async def interact():
    data = await request.json()
    prompt = data.get("prompt", "")

    # pass through translation engine/LLM/Agent
    translated_prompt = await translate_prompt(prompt)
    print(f"Translated prompt: {translated_prompt}")

    # translated_prompt is a list of commands. We have to parse it, and give it to the agent one by one, or maybe we can parallelize tool calls that are isolated, from one another.

    # pass to LLM/Agent (Toolcalls)
    agent_responses = [] 
    for command in translated_prompt:
        agent_response = await call_agent(command)
        agent_responses.append(agent_response)

    ## now the end action of this sorry ass agent is that it can only open the web page. can't do shit after that.

    # we might not even have to retrieve and parse the web page, because the action might be just to take a screenshot, and discard the session of the open browser then. Maybe ...

    # but, how do we do that? how do we get to know if the agent should stop at the screenshot (and not call the ExtractAPI, or if the agent should retreive the web page, and thus call the ExtractAPI?)

    # to control this better, maybe we should have a set of standard responses that the agent can return, because our action vocab is also limited.

    # so, we have a set of standard responses that the agent can return, and we can use that to determine if the agent should stop at the screenshot, or if the agent should retrieve the web page, and thus call the ExtractAPI.
    # Something more is that tool calls can be chained in a partucular way according to the instructions. So, maybe we can build a robust system that can handle this, a little more deterministically.

    # So, level 2 might be this. Instead of constraining our repsonses for InteractAPI, we can let the Playwright function/call('s) return a response, which might not be a end response, but a response that will be passes on to another LLM/Agent, which will interpret what needs to be returned, and returns that as a final response/set of instructiosn (if needed), for the extractAPI to get it's result. I don't know if this makes sense, or not. But, it's a good idea to think about it.

    # so now, how do we get the result of the actions that the agent has performed?
    # we use ExtractAPI. This will be a separate API call, that will be called after the agent has performed all the actions.

    return JSONResponse({"agent_responses": agent_responses})


@app.get("/api/extract")
async def extract():
    data = await request.json()
    run_id = data.get("run_id", "")

    # we need to get the result of the actions that the agent has performed.
    # we use ExtractAPI. This will be a separate API call, that will be called after the agent has performed all the actions.
    
    return JSONResponse({"extract_result": extract_result})


@app.get("/")
async def root():
    return {"message": "Hello, World!"}


@app.get("/health")
async def health_check():
    return JSONResponse({"status": "healthy"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
