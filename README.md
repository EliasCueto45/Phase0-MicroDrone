

# **Phase‑0 Autonomous MicroDrone Wildlife Deterrence System**  
### CONTEXTUAL·AI™ SYSTEMS — RCOS Fall 2026

![CONTEXTUAL·AI SYSTEMS Logo](https://raw.githubusercontent.com/contextualai-systems/Phase0-MicroDrone/refs/heads/main/assets/banner/ContextualAI%20logo.png)

![Phase‑0 QR Code](https://raw.githubusercontent.com/contextualai-systems/Phase0-MicroDrone/refs/heads/main/assets/qr/QR%20Code%20ContextualAI%20Systems.png)

---

## 📄 RCOS Recruitment Deck (Fall 2026)
View the full pitch deck used during the RCOS kickoff session:

[RPI Recruitment Follow-Up Presentation (PDF)](assets/presentations/RPI_Recruitment_Follow_Up_Presentation.pdf)

---


A roof‑mounted autonomous micro‑drone designed to detect wildlife, classify species, execute safe deterrence behaviors, and return to its dock using contextual AI, multi‑axis motion, and strict safety layers.

---

## 🚀 New to the Project? Start Here  

👉 [START_HERE.md](START_HERE.md)


This document explains:

- What Phase‑0 is  
- What you will learn  
- How to get started  
- How to pick your first issue  
- Future semesters & entrepreneurial pathways  

If you’re evaluating this project for RCOS, START_HERE.md is your first stop.

---

## 📄 Student Engineering Packet (2026)  
Complete 51‑page engineering documentation:

- **PDF Version**  
  [https://github.com/contextualai-systems/Phase0-MicroDrone/blob/main/docs/STUDENT%20ENGINEERING%20PACKET%20V3.pdf](https://github.com/contextualai-systems/Phase0-MicroDrone/blob/main/docs/STUDENT%20ENGINEERING%20PACKET%20V3.pdf)

- **DOCX Version**  
  [https://github.com/contextualai-systems/Phase0-MicroDrone/blob/main/docs/STUDENT%20ENGINEERING%20PACKET%20V3.docx](https://github.com/contextualai-systems/Phase0-MicroDrone/blob/main/docs/STUDENT%20ENGINEERING%20PACKET%20V3.docx)

---

## 🧠 System Overview  
The Phase‑0 MicroDrone is built around **five core engineering modules**:

1. **Computer Vision Pipeline**  
2. **Motion Engine**  
3. **Navigation**  
4. **Safety Layer**  
5. **Docking System**

Phase‑0 focuses on architecture, stubs, logging, and test harnesses — not hardware flight.

## 🌟 Why Join This Project?
- Beginner‑friendly tasks  
- Real engineering architecture  
- Clear module structure  
- Future semesters planned  
- Entrepreneurial pathway  
- Opportunity to lead modules  

Phase 0 Architecture Clarification (Final)
This section supersedes both the initial Phase 0 proposal and the updated README changes committed on 9/11 and 9/16. It defines the authoritative architecture for the semester.
Camera Configuration
The drone uses front and downward cameras.
Front camera → forward sensing and general CV pipeline Downward camera → alignment and descent role
The earlier front and rear concept is retired. The rear camera does not serve a role in Phase 0 or Phase 1. The downward camera is required for Phase 1 marker detection and pose estimation. Phase 0 uses synthetic alignment inputs, so the downward camera’s role is defined even if detection is not implemented.
Docking
Phase 0 docking uses synthetic alignment inputs. Real marker detection is optional stretch work. Pose estimation begins in Phase 1.
Docking station design will move toward a larger pad with magnetic capture instead of precise pin alignment. The drone only needs to land within a defined tolerance. The dock handles final mechanical alignment.
Cart Sensor
The cart sensor must detect occupancy and size class.
Required size classes SMALL = bird scale LARGE = human scale
Deterrence is only triggered for bird scale objects. Large objects, including humans, do not trigger deterrence. The drone does not use IR or depth sensors in Phase 0.
Mission Rule
If the cart is in motion, the drone must return to the docking station or enter a defined safe state. Docking on a moving platform is not part of Phase 0 or Phase 1. This is a hard rule.
CV Pipeline
Phase 0 CV uses synthetic frames, preprocessing and timestamped stub observations. No pose estimation. No real marker detection required. The downward camera role is defined but detection can be synthetic.
Drone Rotation
The drone will perform a controlled yaw rotation during sensing. Clockwise or counterclockwise is fine. This improves coverage for both cameras and future sensors.
Environment Setup
Standardized setup for the entire team:
Ubuntu 24.04 Noble PX4 1.17 Gazebo Harmonic ROS 2 Jazzy (hold off installing until I pin exact versions)
PX4 runs the autopilot. Gazebo provides the simulated world. ROS 2 is the bridge between everything. I will post the exact ROS version and installation steps once I finalize the environment.
Module Responsibilities
The architecture is fixed. Module boundaries are fixed. Interfaces are fixed. Environment versions are fixed.
Students have autonomy inside their module, but not in architecture, sensor selection, mission rules, docking logic or environment setup.
Next Steps for the Team
Push your module structure. Update your README to match this architecture. List any blockers. Confirm your module responsibilities. Post any questions.
I will review updates tomorrow afternoon.

---

## 🏗️ Repository Structure  
```
Phase0-MicroDrone/
│
├── assets/                 # QR codes, handouts, presentations
│   ├── qr/                 # QR code images
│   └── presentations/      # RCOS decks + recruitment materials
│
├── docs/                   # Student Engineering Packet (PDF + DOCX)
│
├── cv/                     # Computer vision pipeline
├── motion_engine/          # Multi-axis motion engine
├── safety_layer/           # Safety overrides + constraints
├── docking/                # Docking logic + alignment sensor
│
├── electronics/            # Wiring diagrams + GPIO maps
├── hardware/               # Frame, motors, ESCs, dock components
│
├── simulation/             # Simulation configs (future phases)
├── tests/                  # Unit + integration tests
│
├── src/                    # Main Jetson Nano runtime code
│
├── README.md               # (You are here)
└── LICENSE.md              # MIT License
```

---

## 🖼️ Architecture Summary Diagram  
*(Located in assets/architecture)*

Shows the full autonomy loop:

- Launch from roof dock  
- Autonomous flight and sensing  
- Return‑to‑dock  
- Recharge  
- Ready for next mission  

No cloud compute — fully autonomous.

---

## ⚡ Getting Started (Quick Start)

### Clone the repository
```
git clone https://github.com/contextualai-systems/Phase0-MicroDrone
```

### Install Python dependencies
```
pip install -r requirements.txt
```

### Run the system
```
python3 src/main.py
```

---

## 👥 RCOS Student Teams (Fall 2026)

- Computer Vision  
- Motion Engine  
- Navigation  
- Safety Layer  
- Docking System  
- Electronics + Hardware  
- Simulation (future phases)

---

## 🛠️ Contributing

- Fork the repo  
- Create a feature branch  
- Submit a pull request  
- Follow coding standards in `/docs`  
- Test safety overrides before flight  

Beginner‑friendly tasks are labeled:

- **good first issue**  
- **starter task**  
- **phase:0**


---

## 📬 Contact  
**Jeffrey N. Barat**  
Founder — CONTEXTUAL·AI™ SYSTEMS  
RPI RCOS Project Lead  
Palm Beach Gardens, FL

---
