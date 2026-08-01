import os
import pandas as pd
from context_assembly import load_tables, build_message_bundle
from media_preprocessing import get_media_content

if __name__ == "__main__":
    dataset_dir = "../dataset"
    tables = load_tables(dataset_dir)
    
    df_msg = pd.read_csv(os.path.join(dataset_dir, 'messages.csv'))
    
    img_msgs = df_msg[df_msg['media_type'] == 'image']
    if not img_msgs.empty:
        mid_img = img_msgs.iloc[0]['message_id']
        bundle_img = build_message_bundle(mid_img, tables)
        
        print(f"Testing image message: {mid_img}")
        res_img = get_media_content(bundle_img)
        print("Result:", res_img)
        print("-" * 40)
        
    voice_msgs = df_msg[df_msg['media_type'] == 'voice']
    if not voice_msgs.empty:
        mid_voice = voice_msgs.iloc[0]['message_id']
        bundle_voice = build_message_bundle(mid_voice, tables)
        
        print(f"Testing voice message: {mid_voice}")
        res_voice = get_media_content(bundle_voice)
        print("Result:", res_voice)
        print("-" * 40)
