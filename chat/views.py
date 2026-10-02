import os
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from groq import Groq
from ddgs import DDGS
from .models import ChatMessage

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def chat_view(request):
    history = ChatMessage.objects.all().order_by('created_at')
    return render(request, 'chat/index.html', {'history': history})

def get_live_search_context(query):
    try:
        # DDGS context manager का उपयोग
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        
        if results:
            snippets = [f"- {r.get('title', '')}: {r.get('body', '')}" for r in results]
            context = "\n".join(snippets)
            print("\n=== LIVE SEARCH SUCCESS ===")
            print(context[:250] + "...")
            print("===========================\n")
            return context
    except Exception as e:
        print("Search error:", e)
    return ""

@csrf_exempt
def ask_bot(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_prompt = data.get("message", "").strip()

            if not user_prompt:
                return JsonResponse({"error": "Empty message"}, status=400)

            # 1. सर्च चलाएं
            search_context = get_live_search_context(user_prompt)

            # 2. सिस्टम निर्देश
            system_instruction = (
                "You are an accurate, real-time AI assistant. "
                "Base your answer strictly on the provided Web Search Results. "
                "Current year is 2026. Do not mention cutoff dates."
            )

            # 3. प्रॉम्प्ट तैयार करें
            if search_context:
                full_prompt = f"Web Search Results:\n{search_context}\n\nQuestion: {user_prompt}\nAnswer directly:"
            else:
                full_prompt = user_prompt

            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": full_prompt}
            ]

            # 4. Groq API कॉल
            chat_completion = client.chat.completions.create(
                messages=messages,
                model="openai/gpt-oss-120b",
                max_tokens=250,
            )

            bot_text = chat_completion.choices[0].message.content

            ChatMessage.objects.create(
                user_message=user_prompt,
                bot_response=bot_text
            )

            return JsonResponse({"reply": bot_text})

        except Exception as e:
            print("GROQ ERROR:", e)
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=400)