"""
Test iMessage + Maps integration.
Plan a trip and send the Maps URL via iMessage.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config
from src.agent.maps_agent import MapsAgent
from src.agent.imessage_agent import iMessageAgent


def test_maps_and_imessage():
    """Test planning a trip and sending via iMessage."""
    print("\n" + "="*80)
    print("TEST: Plan Trip + Send via iMessage")
    print("="*80)

    config = load_config()

    # Step 1: Plan the trip
    print("\n1️⃣  Planning trip from Phoenix to LA...")
    maps_agent = MapsAgent(config)

    trip_result = maps_agent.execute("plan_trip_with_stops", {
        "origin": "Phoenix, AZ",
        "destination": "Los Angeles, CA",
        "num_fuel_stops": 1,
        "num_food_stops": 2,
        "departure_time": "4:00 AM"
    })

    if trip_result.get('error'):
        print(f"   ❌ Error planning trip: {trip_result.get('error_message')}")
        return False

    print(f"   ✓ Trip planned successfully")
    print(f"     Origin: {trip_result['origin']}")
    print(f"     Destination: {trip_result['destination']}")
    print(f"     Stops: {trip_result['total_stops']}")

    # Show stops
    for stop in trip_result['stops']:
        icon = "🍴" if stop['type'] == "food" else "⛽"
        print(f"       {stop['order']}. {icon} {stop['location']}")

    maps_url = trip_result['maps_url']
    print(f"\n     Maps URL: {maps_url[:80]}...")

    # Step 2: Send via iMessage
    print("\n2️⃣  Sending trip details via iMessage...")
    imessage_agent = iMessageAgent(config)

    # Compose message
    message = f"""🚗 Your Phoenix to LA trip is planned!

🕐 Departure: 4:00 AM

📍 Stops:
"""
    for stop in trip_result['stops']:
        icon = "🍴" if stop['type'] == "food" else "⛽"
        message += f"{icon} {stop['location']}\n"

    message += f"\n🗺️ Open in Maps:\n{maps_url}"

    # Send the message
    send_result = imessage_agent.execute("send_imessage", {
        "message": message
    })

    if send_result.get('error'):
        print(f"   ❌ Error sending iMessage: {send_result.get('error_message')}")
        print(f"   Note: Make sure Messages.app has accessibility permissions")
        return False

    print(f"   ✓ iMessage sent successfully")
    print(f"     Recipient: {send_result['recipient']}")
    print(f"     Message length: {send_result['message_length']} characters")

    print("\n" + "="*80)
    print("✅ TEST COMPLETED - Check your iPhone for the message!")
    print("="*80)

    return True


if __name__ == "__main__":
    try:
        success = test_maps_and_imessage()
        if not success:
            print("\n⚠️  Test completed with issues")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
