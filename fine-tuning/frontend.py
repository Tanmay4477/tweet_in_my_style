import streamlit as st
from openai import OpenAI

st.title("Tweet Generator")

# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["openai_api_key"])
model_name = st.secrets["model_name"]

# Topic selection
topic = st.selectbox(
    "Choose a topic",
    ["Random", "Coding", "Personal", "Tech", "Funny", "Motivational"]
)

# Generate button
if st.button("Generate Tweet"):
    with st.spinner("Generating..."):
        # Map topic to prompt
        prompt_map = {
            "Random": "Write a tweet in your style and mood",
            "Coding": "Write a tweet about your coding experience",
            "Personal": "Write a personal tweet about your day or feelings",
            "Tech": "Write a tweet about technology or programming",
            "Funny": "Write a funny or witty tweet",
            "Motivational": "Write a motivational tweet for developers"
        }
        
        prompt = prompt_map[topic]
        
        # Generate tweet
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        generated_tweet = response.choices[0].message.content
        st.success(generated_tweet)
        print(generated_tweet)
        
        # Add copy button
        st.button("Copy to clipboard", on_click=lambda: st.write(f"```{generated_tweet}```"))