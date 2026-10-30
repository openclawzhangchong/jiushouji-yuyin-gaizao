import numpy as np, wave, sys
w=wave.open("verify.wav","rb"); x=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(np.float64)/32768
print("len %.1fs  rms %.5f  peak %.4f" % (len(x)/16000, np.sqrt(np.mean(x**2)), np.max(np.abs(x))))
win=1600
env=[np.sqrt(np.mean(x[i:i+win]**2)) for i in range(0,len(x)-win,win)]
env=np.array(env)
print("每秒包络(dBFS):")
for s in range(0,min(46,len(env)//10)):
    seg=env[s*10:(s+1)*10]
    print("  %2ds  min %5.1f  avg %5.1f  max %5.1f" % (s, 20*np.log10(seg.min()+1e-9), 20*np.log10(seg.mean()+1e-9), 20*np.log10(seg.max()+1e-9)))
F=np.abs(np.fft.rfft(x*np.hanning(len(x)))); fr=np.fft.rfftfreq(len(x),1/16000)
band=[(f0,f1,float(np.mean(F[(fr>=f0)&(fr<f1)]))) for f0,f1 in [(0,100),(100,300),(300,1000),(1000,2000),(2000,4000),(4000,8000)]]
print("频谱分带能量:", "  ".join("%d-%d:%.2f"%(a,b,v) for a,b,v in band))
