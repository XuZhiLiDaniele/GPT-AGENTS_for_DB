import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():

    server_params = StdioServerParameters(
        command = sys.executable,
        args=[
            "-u",
            "-m",
            "mcp_server.server"
        ]
    )

    print("\nConnessione al server MCP...")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read,write) as session:
            # Inizializzazione della sessione MCP
            await session.initialize()
            # Scopriamo i tool disponibili
            response = await session.list_tools()

            print("\nTool disponibili:")

            for tool in response.tools:
                print(f"- {tool.name}")
                print(f"  Descrizione: {tool.description}")


if __name__=="__main__":
    asyncio.run(main())