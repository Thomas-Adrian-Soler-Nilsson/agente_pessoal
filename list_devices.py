import sounddevice as sd
 
print(sd.query_devices())
print("\nDispositivo de entrada padrão atual:", sd.default.device)