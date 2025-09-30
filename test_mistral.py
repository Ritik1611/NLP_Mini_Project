# test_mistral.py
print("Attempting to import MistralAI...")

try:
    from mistralai.client import MistralClient
    from mistralai.models.chat_completion import ChatMessage
    print("✅ Success! The mistralai library was imported correctly.")
    print("The problem is with your code editor's configuration.")

except ImportError as e:
    print("\n❌ FAILED to import the library.")
    print(f"Error details: {e}")
    print("This means mistralai is not installed correctly in this environment.")

except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")