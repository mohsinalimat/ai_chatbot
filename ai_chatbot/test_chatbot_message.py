# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
#!/usr/bin/env python3
"""
Check what's in the Chatbot Message that's causing repetitive display
"""

import json
import sys


def check_message_content():
	print("🔍 Checking Chatbot Message Content\n")

	try:
		import frappe

		frappe.init(site="frappe.local")
		frappe.connect()

		# Get the last message with tool_calls
		messages = frappe.get_all(
			"Chatbot Message",
			filters={"role": "assistant", "tool_calls": ["!=", ""]},
			fields=["name", "content", "tool_calls", "timestamp"],
			order_by="timestamp desc",
			limit=1,
		)

		if not messages:
			print("❌ No messages with tool_calls found")
			frappe.destroy()
			return

		msg = messages[0]
		print(f"📝 Message: {msg.name}")
		print(f"⏰ Timestamp: {msg.timestamp}")
		print("\n📄 Content (first 200 chars):")
		print(f"{msg.content[:200]}...")
		print("\n🔧 Tool Calls:")
		print(f"Type: {type(msg.tool_calls)}")
		print(f"Length: {len(msg.tool_calls) if isinstance(msg.tool_calls, str) else 'N/A'}")

		# Try to parse tool_calls
		if msg.tool_calls:
			try:
				if isinstance(msg.tool_calls, str):
					parsed = json.loads(msg.tool_calls)
					print("\n✅ Parsed successfully!")
					print(f"Type after parsing: {type(parsed)}")
					print(f"Length: {len(parsed) if isinstance(parsed, (list, dict)) else 'N/A'}")
					print("\nContent:")
					print(json.dumps(parsed, indent=2))
				else:
					print(f"\n⚠️  Already parsed (type: {type(msg.tool_calls)})")
					print(json.dumps(msg.tool_calls, indent=2))
			except json.JSONDecodeError as e:
				print(f"\n❌ JSON Parse Error: {e}")
				print(f"Raw content: {msg.tool_calls[:500]}")

		# Check full document
		print("\n\n📦 Full Document:")
		doc = frappe.get_doc("Chatbot Message", msg.name)
		print(f"Content length: {len(doc.content)}")
		print(f"Tool calls type: {type(doc.tool_calls)}")

		if doc.tool_calls:
			if isinstance(doc.tool_calls, str):
				print(f"Tool calls string length: {len(doc.tool_calls)}")
				print(f"First 500 chars: {doc.tool_calls[:500]}")
			else:
				print(f"Tool calls: {doc.tool_calls}")

		frappe.destroy()

	except Exception as e:
		print(f"❌ Error: {e}")
		import traceback

		traceback.print_exc()


if __name__ == "__main__":
	check_message_content()
