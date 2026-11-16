import streamlit as st
import cv2
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
load_dotenv()                       

host = os.getenv(DB_HOST)
password = os.getenv(DB_PASSWORD) 
user = os.getenv(DB_USER)
port = os.getenv(DB_PORT)
database = os.getenv(DB_NAME)

engine = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}")

EVENT_ID = 4

st.title(" 受付 & 配布管理 / Check-in & Item tracking")

img_file = st.camera_input("QRコードを撮影してください / Please scan the QR code")

st.markdown("""
    <style>
    audio {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

if img_file is not None:
    file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(img)

    if not data:
        st.error("QRコードを読み取れませんでした。もう一度試してください。/ QR code could not be read. Please try again.")
        st.audio("error_audio_path", format="audio/mp3", autoplay=True)
    else:
        with engine.begin() as conn:
            # 参加者確認
            person = conn.execute(text("""
                SELECT p.name, er.registration_id, er.attended
                FROM people p
                JOIN event_registration er ON p.person_id = er.person_id
                WHERE p.email = :email AND er.event_id = :event_id
            """), {"email": data, "event_id": EVENT_ID}).fetchone()

            if person is None:
                st.error(f"❌ 参加登録が見つかりません / Registration not found: {data}")
                st.audio("error_audio_path", format="audio/mp3", autoplay=True)
            else:
                name, registration_id, attended = person

                # チェックイン処理
                if attended == 1:
                    st.warning(f"⚠️ {name} さんはすでにチェックイン済みです / {name} has already checked in")
                    st.audio("checkin_audio_path", format="audio/mp3", autoplay=True)
                else:
                    conn.execute(text("""
                        UPDATE event_registration SET attended = 1
                        WHERE registration_id = :registration_id
                    """), {"registration_id": registration_id})
                    st.success(f"✅ ようこそ、{name} さん！チェックイン完了 / Welcome, {name}! Check-in completed")
                    st.balloons()
                    st.audio("success_audio_path", format="audio/mp3", autoplay=True)

                st.divider()

                # track item distribution
                items = conn.execute(text("""
                    SELECT i.item_id, i.item_name, i.max_per_person,
                        COUNT(d.distribution_id) as given_count
                    FROM item i
                    LEFT JOIN item_distribution d
                        ON d.item_id = i.item_id
                        AND d.registration_id = :registration_id
                    WHERE i.event_id = :event_id
                    GROUP BY i.item_id
                """), {"registration_id": registration_id, "event_id": EVENT_ID}).fetchall()

                # track item variants
                variants = conn.execute(text("""
                    SELECT v.variant_id, v.variant_name, v.total_quantity,
                        COUNT(d.distribution_id) as given_count
                    FROM item_variant v
                    LEFT JOIN item_distribution d ON d.variant_id = v.variant_id
                    WHERE v.item_id = 1
                    GROUP BY v.variant_id
                """)).fetchall()

                st.subheader("配布状況")
                for item in items:
                    col1, col2, col3 = st.columns([3, 2, 2])
                    with col1:
                        st.write(item.item_name)
                    with col2:
                        st.write(f"{item.given_count} / {item.max_per_person}")
                    with col3:
                        if item.given_count >= item.max_per_person:
                            st.write("✅ 配布済み")
                        else:
                            if item.item_id == 1:
                                available_variants = [v for v in variants if v.given_count < v.total_quantity]
                                variant_options = {v.variant_name: v.variant_id for v in available_variants}

                                if not variant_options:
                                    st.write("⚠️ 在庫なし")
                                else:
                                    selected = st.selectbox(
                                        "種類を選択",
                                        options=list(variant_options.keys()),
                                        key=f"variant_{registration_id}"
                                    )
                                    if st.button("渡す", key=f"btn_{item.item_id}"):
                                        with engine.begin() as conn2:
                                            conn2.execute(text("""
                                                INSERT INTO item_distribution (registration_id, item_id, variant_id)
                                                VALUES (:registration_id, :item_id, :variant_id)
                                            """), {
                                                "registration_id": registration_id,
                                                "item_id": item.item_id,
                                                "variant_id": variant_options[selected]
                                            })
                                        st.success(f"🍙 {selected}を渡しました！")
                                        st.rerun()
                            else:
                                if st.button("渡す", key=f"btn_{item.item_id}"):
                                    with engine.begin() as conn2:
                                        conn2.execute(text("""
                                            INSERT INTO item_distribution (registration_id, item_id)
                                            VALUES (:registration_id, :item_id)
                                        """), {"registration_id": registration_id, "item_id": item.item_id})
                                    st.success(f"🍡 {item.item_name}を渡しました！")
                                    st.rerun()