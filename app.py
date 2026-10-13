from flask import Flask,jsonify,render_template,request
import json,time,os,hmac
from pathlib import Path

app=Flask(__name__)

@app.before_request
def authorize_request():
 if request.path=="/health":return None
 if request.path.startswith("/internal/"):
  expected=os.environ.get("MURMUR_INTERNAL_TOKEN","")
  supplied=request.headers.get("Authorization","")
  if not expected or not hmac.compare_digest(supplied,"Bearer "+expected):return jsonify({"error":"unauthorized"}),401
  return None
 user=os.environ.get("MURMUR_DASHBOARD_USER","")
 password=os.environ.get("MURMUR_DASHBOARD_PASSWORD","")
 auth=request.authorization
 if not user or not password or not auth or not hmac.compare_digest(auth.username,user) or not hmac.compare_digest(auth.password,password):
  return ("Authentication required",401,{"WWW-Authenticate":'Basic realm="Murmur"'})

@app.template_global()
def cst(s):
 try:
  from datetime import datetime,timedelta
  return (datetime.fromisoformat(s)+timedelta(hours=8)).strftime("%m-%d %H:%M")
 except:return s

DATA_DIR=Path(os.environ.get("MURMUR_DATA_DIR","/data/murmur"))
DATA_DIR.mkdir(parents=True,exist_ok=True)
STATE=DATA_DIR/"state.json"
ARC=DATA_DIR/"arc.jsonl"
REGRET=DATA_DIR/"regret.jsonl"
MEM_LONG=DATA_DIR/"memory_long.txt"
MEM_SHORT=DATA_DIR/"memory_short.txt"
LAST=DATA_DIR/"last_result.json"
CMD=DATA_DIR/"cmd.json"
ORDER=["attachment","tenderness","heartache","curiosity","mischief","restless","regret","desire","gloom","jealousy"]

@app.route("/health")
def health():
 return jsonify({"status":"ok"})

@app.route("/")
def index():
 drives=[];top_drive=None
 if STATE.exists():
  s=json.loads(STATE.read_text(encoding="utf-8"))
  d=s.get("drives",{})
  if d:
   tk=max(d,key=lambda k:d[k]["v"])
   drives=[(k,d[k],k==tk) for k in ORDER if k in d]
   top_drive=d[tk]
 arcs=[]
 if ARC.exists():
  lines=[json.loads(l) for l in ARC.read_text(encoding="utf-8").splitlines() if l.strip()]
  arcs=list(reversed(lines[-50:]))
 regrets=[]
 if REGRET.exists():
  lines=[json.loads(l) for l in REGRET.read_text(encoding="utf-8").splitlines() if l.strip()]
  regrets=list(reversed(lines[-20:]))
 return render_template("index.html",drives=drives,arcs=arcs,top_drive=top_drive,regrets=regrets)

@app.route("/api/state")
def api_state():
 if STATE.exists():return jsonify(json.loads(STATE.read_text(encoding="utf-8")))
 return jsonify({})

@app.route("/api/arc")
def api_arc():
 if not ARC.exists():return jsonify([])
 lines=[json.loads(l) for l in ARC.read_text(encoding="utf-8").splitlines() if l.strip()]
 arc_type=request.args.get("type")
 if arc_type:lines=[l for l in lines if l.get("type")==arc_type]
 return jsonify(lines[-50:])

@app.route("/api/regret")
def api_regret():
 if not REGRET.exists():return jsonify([])
 lines=[json.loads(l) for l in REGRET.read_text(encoding="utf-8").splitlines() if l.strip()]
 return jsonify(lines[-50:])

@app.route("/api/memory")
def api_memory():
 long=MEM_LONG.read_text(encoding="utf-8").strip() if MEM_LONG.exists() else ""
 short=MEM_SHORT.read_text(encoding="utf-8").strip() if MEM_SHORT.exists() else ""
 return jsonify({"long":long,"short":short})

@app.route("/api/activate",methods=["POST"])
def activate():
 data=request.get_json(force=True)
 if LAST.exists():
  try:LAST.unlink()
  except:pass
 with open(CMD,"w",encoding="utf-8") as f:
  json.dump(data,f,ensure_ascii=False)
 t=data.get("type","")
 if t in("boost","write_arc"):
  for _ in range(150):
   time.sleep(0.1)
   if LAST.exists():
    return jsonify(json.loads(LAST.read_text(encoding="utf-8")))
  return jsonify({"ok":True,"warn":"timeout"})
 return jsonify({"ok":True})

if __name__=="__main__":
 app.run(host="0.0.0.0",port=8080,debug=False)

@app.route("/internal/v1/chats/<chat_id>/emotion/<operation>",methods=["GET","POST"])
@app.route("/internal/v1/chats/<chat_id>/emotion",methods=["GET","POST"])
def internal_emotion(chat_id,operation="state"):
 if operation not in ("state","arc","history","regret","memory","activate"):return jsonify({"error":"unknown_emotion_operation"}),404
 if request.method=="GET":
  if operation=="state":
   state=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
   drives=state.get("drives",{})
   top=max(drives.items(),key=lambda item:item[1].get("v",0)) if drives else ("attachment",{"v":0.4,"z":"想念","b":0.4})
   return jsonify({"time":state.get("time"),"drives":drives,"top":{"drive":top[0],"value":top[1].get("v",0),"label":top[1].get("z","")},"offlineTicks":state.get("offlineTicks",0)})
  if operation=="arc":
   lines=[json.loads(line) for line in ARC.read_text(encoding="utf-8").splitlines() if line.strip()] if ARC.exists() else []
   kind=request.args.get("type")
   if kind:lines=[line for line in lines if line.get("type")==kind]
   return jsonify(lines[-max(1,min(200,int(request.args.get("n",50)))):])
  if operation=="regret":
   lines=[json.loads(line) for line in REGRET.read_text(encoding="utf-8").splitlines() if line.strip()] if REGRET.exists() else []
   return jsonify(lines[-max(1,min(200,int(request.args.get("n",50)))):])
  if operation=="memory":
   return jsonify({"long":MEM_LONG.read_text(encoding="utf-8").strip() if MEM_LONG.exists() else "","short":MEM_SHORT.read_text(encoding="utf-8").strip() if MEM_SHORT.exists() else ""})
  if operation=="history":
   return jsonify([])
  return jsonify({"error":"method_not_allowed"}),405
 data=request.get_json(silent=True) or {}
 if operation=="memory" or data.get("type")=="write_memory":
  field=MEM_LONG if data.get("scope")=="long" else MEM_SHORT
  maximum=20000 if field==MEM_LONG else 500
  field.write_text(str(data.get("content",""))[:maximum],encoding="utf-8")
  return jsonify({"ok":True,"scope":"long" if field==MEM_LONG else "short","length":len(field.read_text(encoding="utf-8"))})
 if LAST.exists():
  try:LAST.unlink()
  except:pass
 CMD.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
 if data.get("type") in ("boost","write_arc"):
  for _ in range(50):
   time.sleep(.1)
   if LAST.exists():return jsonify(json.loads(LAST.read_text(encoding="utf-8")))
 return jsonify({"ok":True})
