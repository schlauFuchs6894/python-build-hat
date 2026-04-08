NameError: name 'hat' is not defined. Did you mean: 'Hat'?
(venv) vali@Pi5-Vali:~/WRO/repo/python-build-hat/test $ python - <<'EOF'
from buildhat import Hat, Motor, ColorDistanceSensor

hat = Hat(device="/dev/ttyAMA4", reset_gpio=25, boot0_gpio=24, debug=True)

print(hat.get())
EOF
{'A': {'typeid': 38, 'connected': True, 'name': 'Motor', 'description': 'Medium Linear Motor'},
 'B': {'typeid': -1, 'connected': False, 'name': 'Disconnected', 'description': ''},
 'C': {'typeid': -1, 'connected': False, 'name': 'Disconnected', 'description': ''},
 'D': {'typeid': 48, 'connected': True, 'name': 'Motor', 'description': 'Medium Angular Motor (Cyan)'}}
(venv) vali@Pi5-Vali:~/WRO/repo/python-build-hat/test $


#############################################################

python - <<'EOF'
from buildhat import Hat, Motor, ColorDistanceSensor
from gpiozero import OutputDevice
# Read HAT 1
rstH2 = OutputDevice(25, active_high=True, initial_value=True)
print("H2 GPIO25 Reset high")
rstH2.off()

h1 = Hat(
    device="/dev/ttyAMA0",
    reset_gpio=4,
    boot0_gpio=22,
    debug=False,
)
print("HAT1:")
print(h1.get())

h1=Hat()
print(h1.get())

EOF



#############################################################


python - <<'EOF'
from buildhat import Hat, Motor, ColorDistanceSensor
from gpiozero import OutputDevice

# Read HAT 2
"""Test getting list of devices"""
rstH2 = OutputDevice(25, active_high=True, initial_value=False)
rstH1 = OutputDevice(4, active_high=True, initial_value=True)
print("H1 GPIO4 Reset high")
rstH1.off()

h2 = Hat(
    device="/dev/ttyAMA4",
    reset_gpio=05,
    boot0_gpio=06,
    debug=False,
)
print("HAT2:")
print(h2.get())

EOF




