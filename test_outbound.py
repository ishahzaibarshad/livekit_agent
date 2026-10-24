"""
Test script for Twilio outbound calling

Usage:
    python test_outbound.py --to "+14155551234" --url "https://your-ngrok-url.ngrok.io"

Or edit the defaults below and run:
    python test_outbound.py
"""

import argparse
import requests
import json
import sys
from dotenv import load_dotenv
import os

load_dotenv()


def place_test_call(to_number: str, webhook_base_url: str, server_url: str = "http://localhost:8000"):
    """Place a test outbound call"""

    print("=" * 60)
    print("Twilio Outbound Call Test")
    print("=" * 60)
    print(f"Server URL: {server_url}")
    print(f"Webhook Base URL: {webhook_base_url}")
    print(f"Calling: {to_number}")
    print("=" * 60)

    # Prepare request
    url = f"{server_url}/api/outbound/call"
    payload = {
        "to_number": to_number,
        "webhook_base_url": webhook_base_url
    }

    print(f"\nSending request to: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        # Make the API call
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        print(f"\nResponse Status: {response.status_code}")

        # Parse response
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")

            if result.get("success"):
                print("\n✅ SUCCESS!")
                print(f"   Call SID: {result.get('call_sid')}")
                print(f"   Status: {result.get('status')}")
                print(f"   Room Name: {result.get('room_name')}")
                print(f"   WebSocket URL: {result.get('websocket_url')}")
                print(f"\n🎉 The phone should ring shortly!")
                print(f"\n📊 Monitor call status at:")
                print(f"   https://console.twilio.com/monitor/logs/calls/{result.get('call_sid')}")
            else:
                print(f"\n❌ FAILED: {result.get('error')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False

        return True

    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to server at {server_url}")
        print("   Make sure the server is running:")
        print("   python main.py start")
        print("   OR")
        print("   uvicorn main:app --reload")
        return False

    except requests.exceptions.Timeout:
        print(f"\n❌ ERROR: Request timed out")
        return False

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test Twilio outbound calling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_outbound.py --to "+14155551234" --url "https://abc123.ngrok.io"
  python test_outbound.py --to "+14155551234" --url "https://abc123.ngrok.io" --server "http://localhost:8000"
        """
    )

    parser.add_argument(
        "--to",
        type=str,
        default=os.getenv("TEST_PHONE_NUMBER", ""),
        help="Phone number to call (E.164 format, e.g., +14155551234)"
    )

    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("WEBHOOK_BASE_URL", ""),
        help="Public webhook base URL (e.g., https://abc123.ngrok.io)"
    )

    parser.add_argument(
        "--server",
        type=str,
        default="http://localhost:8000",
        help="Local server URL (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.to:
        print("❌ ERROR: Phone number is required")
        print("Use: --to '+14155551234'")
        sys.exit(1)

    if not args.to.startswith("+"):
        print("❌ ERROR: Phone number must be in E.164 format (start with +)")
        print("Example: +14155551234")
        sys.exit(1)

    if not args.url:
        print("❌ ERROR: Webhook base URL is required")
        print("\nSteps to get webhook URL:")
        print("1. Install ngrok: https://ngrok.com/download")
        print("2. Run: ngrok http 8000")
        print("3. Copy the HTTPS URL (e.g., https://abc123.ngrok.io)")
        print("4. Use: --url 'https://abc123.ngrok.io'")
        print("\nOr set WEBHOOK_BASE_URL in .env file")
        sys.exit(1)

    # Test the call
    success = place_test_call(
        to_number=args.to,
        webhook_base_url=args.url,
        server_url=args.server
    )

    if success:
        print("\n" + "=" * 60)
        print("Next steps:")
        print("1. Answer the phone when it rings")
        print("2. Check server logs to see Media Stream connection")
        print("3. Monitor Twilio debugger: https://console.twilio.com/monitor/logs/debugger")
        print("=" * 60)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
