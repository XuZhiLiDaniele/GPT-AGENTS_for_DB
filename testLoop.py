
import asyncio


async def main():

    print("================================")
    print("TEST LOOP")
    print("Scrivi exit per uscire")
    print("================================")

    while True:

        user_input = input("\nYou: ").strip()

        print(f"[DEBUG] Ricevuto: {user_input}")

        if user_input.lower() in ["exit", "quit"]:

            print("Goodbye!")

            break

        print("[DEBUG] Sto elaborando la richiesta...")

        # Simuliamo una risposta
        await asyncio.sleep(1)

        print("Assistant: Ho ricevuto la tua richiesta.")

        print("[DEBUG] Torno al loop...")


if __name__ == "__main__":
    asyncio.run(main())