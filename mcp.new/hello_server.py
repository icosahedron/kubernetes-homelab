#!/usr/bin/env python3
"""
Hello MCP server using Python SDK
"""

import asyncio
from mcp import server, McpError, ErrorCode
from mcp.transport.stdio import StdioServerTransport
from mcp.model import Tool, Parameter

# Async function to run the MCP server
async def run_server():
    # Initialize the server with name and version
    server = Server(name="python-text-tools", version="0.2.0")

    # Define the 'hello' tool
    @server.tool(
        name="hello",
        description="Says hello to a given name or the world.",
        parameters=[
            Parameter(name="name", type="string", description="The name to say hello to.", required=False)
        ]
    )
    async def hello_tool(name: str = "world"):
        """Handler for the 'hello' tool."""
        greeting = f"Hello, {name}!"
        return {"content": [{"type": "text", "text": greeting}]}

    # Define the 'reverse' tool
    @server.tool(
        name="reverse",
        description="Reverses the given text string.",
        parameters=[
            Parameter(name="text", type="string", description="The text to reverse.", required=True)
        ]
    )
    async def reverse_tool(text: str):
        """Handler for the 'reverse' tool."""
        if not text:
             # Although parameter is required, handle empty string case if needed
             # Or rely on mcp library validation if it handles empty strings for required params
             return {"content": [{"type": "text", "text": ""}]}
        reversed_text = text[::-1]
        return {"content": [{"type": "text", "text": reversed_text}]}

    # Connect server over stdio transport
    transport = StdioServerTransport()
    await server.connect(transport)

# Entry point
if __name__ == "__main__":
    asyncio.run(run_server())
