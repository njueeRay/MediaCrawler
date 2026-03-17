# MediaCrawler 閮ㄧ讲鏂囨。

> 鏈枃妗ｈ鐩?Docker 涓?systemd 鍙岃建閮ㄧ讲鏂规锛岄€傜敤浜庣敓浜т笌杞婚噺鐜銆?

---

## 涓€銆佺幆澧冨噯澶?
- [ ] 鍏嬮殕椤圭洰锛歚git clone https://github.com/xxx/MediaCrawler.git`
- [ ] Python 3.9+銆丯ode.js 16+銆丮ongoDB銆丷edis
- [ ] 瀹夎渚濊禆锛?
  - `pip install -r requirements.txt`
  - `npm install`锛堝墠绔闇€鏋勫缓锛?
- [ ] 閰嶇疆 .env 鏂囦欢锛堝弬鑰?.env.example锛?

---

## 浜屻€丏ocker 閮ㄧ讲锛堟帹鑽愯交閲?涓€閿紡锛?

### 1. 鏋勫缓闀滃儚
```bash
docker build -t mediacrawler:latest .
```

### 2. 鍚姩瀹瑰櫒
```bash
docker run -d \
  --name mediacrawler \
  -p 8000:8000 \
  --env-file .env \
  mediacrawler:latest
```

### 3. 鏁版嵁鎸佷箙鍖栵紙鍙€夛級
```bash
docker run -d \
  --name mediacrawler \
  -p 8000:8000 \
  --env-file .env \
  -v /data/mongo:/data/db \
  -v /data/redis:/data/redis \
  mediacrawler:latest
```

---

## 涓夈€乻ystemd 閮ㄧ讲锛堟帹鑽愮敓浜?楂樺彲鐢級

### 1. 鍒涘缓铏氭嫙鐜
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 鍚姩鏈嶅姟
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. 缂栧啓 systemd 鏈嶅姟鏂囦欢
`/etc/systemd/system/mediacrawler.service`
```ini
[Unit]
Description=MediaCrawler FastAPI Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/MediaCrawler
EnvironmentFile=/path/to/MediaCrawler/.env
ExecStart=/path/to/MediaCrawler/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. 鍚敤骞跺惎鍔ㄦ湇鍔?
```bash
sudo systemctl daemon-reload
sudo systemctl enable mediacrawler
sudo systemctl start mediacrawler
```

---

## 鍥涖€佸父瑙侀棶棰?
- [ ] 绔彛鍐茬獊锛氫慨鏀?.env 鎴?systemd 閰嶇疆
- [ ] MongoDB/Redis 杩炴帴澶辫触锛氭鏌?.env 閰嶇疆涓庢湇鍔＄姸鎬?
- [ ] 鍓嶇鏋勫缓澶辫触锛氱‘璁?Node.js 鐗堟湰涓庝緷璧?
- [ ] 鏃ュ織寮傚父锛氭鏌?logs/ 鐩綍涓?systemd 鏃ュ織

---

> 濡傞渶璇︾粏閰嶇疆璇存槑锛屽弬鑰?docs/meetings/2026-02-27-full-team-open-discussion.md 涓?.env.example銆?

