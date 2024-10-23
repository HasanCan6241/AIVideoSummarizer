import os
import threading
from django.shortcuts import render
from moviepy.editor import VideoFileClip
import speech_recognition as sr
from transformers import BertTokenizerFast, EncoderDecoderModel
from youtube_transcript_api import YouTubeTranscriptApi


ckpt = 'mrm8488/bert2bert_shared-turkish-summarization'
same_pipe_token = BertTokenizerFast.from_pretrained(ckpt)
same_pipe_model = EncoderDecoderModel.from_pretrained(ckpt)

# Özetleme fonksiyonu
def generate_summary(text):
    inputs = same_pipe_token([text], padding="max_length", truncation=True, max_length=512, return_tensors="pt")
    input_ids = inputs.input_ids
    attention_mask = inputs.attention_mask
    output = same_pipe_model.generate(input_ids, attention_mask=attention_mask)
    return same_pipe_token.decode(output[0], skip_special_tokens=True)

# Ses çıkarma fonksiyonu
def extract_audio(video_path, audio_path):
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path)

# Konuşma tanıma fonksiyonu
def recognize_speech(audio_path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio, language="tr-TR")
        except sr.UnknownValueError:
            return "Ses anlaşılamadı."
        except sr.RequestError as e:
            return f"Google API hatası: {e}"
def video_summary(request):
    if request.method == "POST" and request.FILES.get('video'):
        video_file = request.FILES['video']

        video_path = os.path.join("media", video_file.name)
        with open(video_path, 'wb+') as destination:
            for chunk in video_file.chunks():
                destination.write(chunk)

        audio_path = os.path.splitext(video_path)[0] + ".wav"
        speech_text = {}

        def process_video():
            extract_audio(video_path, audio_path)
            speech_text['text'] = recognize_speech(audio_path)

        video_thread = threading.Thread(target=process_video)
        video_thread.start()
        video_thread.join()

        summary = generate_summary(speech_text['text'])

        context = {
            'text': speech_text['text'],
            'summary': summary
        }
        return render(request, 'summarizer/video-summary.html', context)

    return render(request, 'summarizer/video-summary.html')


# YouTube video ID'sini linkten almak için bir fonksiyon
def get_video_id(youtube_url):
    if "v=" in youtube_url:
        return youtube_url.split("v=")[1].split("&")[0]
    elif "youtu.be" in youtube_url:
        return youtube_url.split("/")[-1]
    else:
        raise ValueError("Geçersiz YouTube linki")


# YouTube videosunun transcriptini alma
def get_video_transcript(youtube_url, language='tr'):
    try:
        video_id = get_video_id(youtube_url)
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
        video_text = " ".join([entry['text'] for entry in transcript])
        return video_text
    except Exception as e:
        return str(e)

def youtube_summary(request):
    if request.method == "POST":
        youtube_url = request.POST.get("youtube_url")
        transcript_text = get_video_transcript(youtube_url, language='tr')

        if transcript_text.startswith("Geçersiz"):
            context = {
                'error': "Geçersiz YouTube linki veya altyazı bulunamadı."
            }
        else:
            # Özetleme işlemi
            summary = generate_summary(transcript_text)

            context = {
                'transcript': transcript_text,
                'summary': summary
            }
        return render(request, 'summarizer/youtube_summary.html', context)

    return render(request, 'summarizer/youtube_summary.html')

def index(request):
    return render(request,'summarizer/index.html')