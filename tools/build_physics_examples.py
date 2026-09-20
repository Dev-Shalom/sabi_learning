#!/usr/bin/env python
"""Generate the Physics worked examples, with every answer computed.

Not a convenience. The product's whole claim is that it is not confidently
wrong, and a worked example with a typo in its final line is exactly the kind
of wrong that is hardest to catch by reading. So no number in the output is
typed: each example states its givens, the arithmetic is done here, and the
stated answer is formatted from the computed value.

`tests/test_physics_corpus.py` then recomputes the same quantities
independently from the markdown, so the corpus is checked by something that
did not produce it.

    python tools/build_physics_examples.py

WAEC convention throughout: g = 10 m/s².
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "corpus" / "physics" / "examples"
G = 10.0


def n(value: float, dp: int = 2) -> str:
    """A number as a student would write it: no trailing zeros, no -0."""
    rounded = round(value + 0.0, dp)
    if rounded == int(rounded):
        return str(int(rounded))
    text = f"{rounded:.{dp}f}".rstrip("0").rstrip(".")
    return text if text != "-0" else "0"


def doc(
    *,
    num: int,
    slug: str,
    title: str,
    topic: str,
    subtopic: str,
    section: str,
    question: str,
    steps: list[str],
    answer: str,
) -> tuple[str, str]:
    """One worked example, in the same shape as the Mathematics corpus."""
    body = "\n".join(f"{i}. {line}" for i, line in enumerate(steps, start=1))
    text = f"""---
doc_id: phy-ex-{num:02d}-{slug}
title: {title}
source: Sabi worked example, WAEC Paper 2 style
attribution: worked_example
topic: {topic}
subtopic: {subtopic}
syllabus_section: {section}
exam_board: WAEC
subject: Physics
level: SS3
locator: PEX {num}
---

## Question

{question}

## Solution

{body}

**Answer: {answer}**
"""
    return f"phy-ex-{num:02d}-{slug}.md", text


EXAMPLES: list[tuple[str, str]] = []


# ---------------------------------------------------------------- 1. motion
u, v, t = 0.0, 20.0, 8.0
a = (v - u) / t
s = u * t + 0.5 * a * t * t
EXAMPLES.append(doc(
    num=1, slug="uniform-acceleration", title="Acceleration and distance from rest",
    topic="Measurement and mechanics", subtopic="Linear motion", section="A3",
    question=(
        f"A car starts from rest and reaches a speed of {n(v)} m/s in {n(t)} s. "
        "Find (a) its acceleration, (b) the distance it covers in that time."
    ),
    steps=[
        "Write down what is given: u = 0 m/s, v = "
        f"{n(v)} m/s, t = {n(t)} s.",
        "Part (a). Acceleration is the rate of change of velocity, "
        "a = (v − u) / t.",
        f"a = ({n(v)} − {n(u)}) / {n(t)} = {n(a)} m/s².",
        "Part (b). With uniform acceleration from rest, s = ut + ½at².",
        f"s = 0 + ½ × {n(a)} × {n(t)}² = ½ × {n(a)} × {n(t*t)}.",
        f"s = {n(s)} m.",
    ],
    answer=f"(a) {n(a)} m/s²  (b) {n(s)} m",
))

# ------------------------------------------------------------- 2. free fall
h = 45.0
t_fall = (2 * h / G) ** 0.5
v_hit = G * t_fall
EXAMPLES.append(doc(
    num=2, slug="free-fall", title="Time and speed of a falling object",
    topic="Measurement and mechanics", subtopic="Linear motion", section="A3",
    question=(
        f"A stone is dropped from rest from a height of {n(h)} m. "
        "Taking g = 10 m/s² and ignoring air resistance, find (a) the time it "
        "takes to reach the ground, (b) the speed with which it lands."
    ),
    steps=[
        f"Given: u = 0 m/s, h = {n(h)} m, g = {n(G)} m/s².",
        "Part (a). Falling from rest, h = ½gt², so t = √(2h / g).",
        f"t = √(2 × {n(h)} / {n(G)}) = √{n(2*h/G)}.",
        f"t = {n(t_fall)} s.",
        "Part (b). The speed on landing is v = gt.",
        f"v = {n(G)} × {n(t_fall)} = {n(v_hit)} m/s.",
    ],
    answer=f"(a) {n(t_fall)} s  (b) {n(v_hit)} m/s",
))

# ------------------------------------------------------------ 3. v-t graph
v_peak, t_acc, t_const, t_dec = 15.0, 4.0, 6.0, 5.0
d_acc = 0.5 * v_peak * t_acc
d_const = v_peak * t_const
d_dec = 0.5 * v_peak * t_dec
d_total = d_acc + d_const + d_dec
EXAMPLES.append(doc(
    num=3, slug="velocity-time-graph", title="Distance from a velocity-time graph",
    topic="Measurement and mechanics", subtopic="Linear motion", section="A3",
    question=(
        f"A bus accelerates uniformly from rest to {n(v_peak)} m/s in {n(t_acc)} s, "
        f"travels at that speed for {n(t_const)} s, then decelerates uniformly to "
        f"rest in a further {n(t_dec)} s. Find the total distance it covers."
    ),
    steps=[
        "On a velocity-time graph the distance is the area under the line, so "
        "take the journey in three parts.",
        f"Accelerating: a triangle of base {n(t_acc)} s and height {n(v_peak)} m/s, "
        f"area = ½ × {n(t_acc)} × {n(v_peak)} = {n(d_acc)} m.",
        f"Constant speed: a rectangle, area = {n(v_peak)} × {n(t_const)} = "
        f"{n(d_const)} m.",
        f"Decelerating: a triangle of base {n(t_dec)} s and height {n(v_peak)} m/s, "
        f"area = ½ × {n(t_dec)} × {n(v_peak)} = {n(d_dec)} m.",
        f"Total distance = {n(d_acc)} + {n(d_const)} + {n(d_dec)}.",
        f"= {n(d_total)} m.",
    ],
    answer=f"{n(d_total)} m",
))

# ----------------------------------------------------------- 4. projectile
u_proj, angle_sin = 40.0, 0.5   # 30 degrees, sin 30 = 0.5, cos 30 = 0.866...
angle_cos = (3 ** 0.5) / 2
t_flight = 2 * u_proj * angle_sin / G
range_ = u_proj * angle_cos * t_flight
EXAMPLES.append(doc(
    num=4, slug="projectile-range", title="Time of flight and range of a projectile",
    topic="Measurement and mechanics", subtopic="Projectile motion", section="A4",
    question=(
        f"A ball is projected from level ground at {n(u_proj)} m/s at 30° to the "
        "horizontal. Taking g = 10 m/s², find (a) its time of flight, (b) its "
        "horizontal range."
    ),
    steps=[
        f"Resolve the launch velocity. Vertical: u sin30 = {n(u_proj)} × 0.5 = "
        f"{n(u_proj*angle_sin)} m/s. Horizontal: u cos30 = {n(u_proj)} × 0.866 = "
        f"{n(u_proj*angle_cos)} m/s.",
        "Part (a). Over level ground the time of flight is T = 2u sinθ / g.",
        f"T = (2 × {n(u_proj)} × 0.5) / {n(G)} = {n(t_flight)} s.",
        "Part (b). The horizontal velocity does not change, so R = u cosθ × T.",
        f"R = {n(u_proj*angle_cos)} × {n(t_flight)} = {n(range_)} m.",
    ],
    answer=f"(a) {n(t_flight)} s  (b) {n(range_)} m (about {n(range_, 0)} m)",
))

# ------------------------------------------------------------ 5. F = ma
mass_car, a_car = 1200.0, 2.5
force = mass_car * a_car
EXAMPLES.append(doc(
    num=5, slug="newton-second-law", title="Force from mass and acceleration",
    topic="Measurement and mechanics", subtopic="Newton's laws", section="A6",
    question=(
        f"A car of mass {n(mass_car)} kg accelerates uniformly at {n(a_car)} m/s². "
        "Find the resultant force acting on it."
    ),
    steps=[
        "Newton's second law: the resultant force equals mass times acceleration, "
        "F = ma.",
        f"F = {n(mass_car)} × {n(a_car)}.",
        f"F = {n(force)} N.",
        "The force is in the same direction as the acceleration.",
    ],
    answer=f"{n(force)} N",
))

# ---------------------------------------------------------- 6. momentum
m1, u1, m2, u2 = 3.0, 4.0, 2.0, 0.0
v_combined = (m1 * u1 + m2 * u2) / (m1 + m2)
EXAMPLES.append(doc(
    num=6, slug="momentum-collision", title="Velocity after an inelastic collision",
    topic="Measurement and mechanics", subtopic="Momentum", section="A6",
    question=(
        f"A trolley of mass {n(m1)} kg moving at {n(u1)} m/s collides with a "
        f"stationary trolley of mass {n(m2)} kg. They stick together after the "
        "collision. Find their common velocity."
    ),
    steps=[
        "Momentum is conserved in a collision, so total momentum before equals "
        "total momentum after.",
        f"Before: p = m₁u₁ + m₂u₂ = ({n(m1)} × {n(u1)}) + ({n(m2)} × {n(u2)}) = "
        f"{n(m1*u1 + m2*u2)} kg m/s.",
        f"After: the two move together with a combined mass of {n(m1)} + {n(m2)} = "
        f"{n(m1+m2)} kg, so p = {n(m1+m2)}v.",
        f"Setting them equal: {n(m1+m2)}v = {n(m1*u1 + m2*u2)}.",
        f"v = {n(m1*u1 + m2*u2)} / {n(m1+m2)} = {n(v_combined)} m/s.",
    ],
    answer=f"{n(v_combined)} m/s in the direction of the first trolley",
))

# -------------------------------------------------------- 7. work and power
force_w, dist_w, time_w = 250.0, 12.0, 6.0
work = force_w * dist_w
power = work / time_w
EXAMPLES.append(doc(
    num=7, slug="work-and-power", title="Work done and power developed",
    topic="Energy", subtopic="Work, energy and power", section="B1",
    question=(
        f"A man pushes a crate {n(dist_w)} m along the floor with a steady force "
        f"of {n(force_w)} N in the direction of motion, taking {n(time_w)} s. "
        "Find (a) the work he does, (b) the power he develops."
    ),
    steps=[
        "Part (a). Work is force times distance moved in the direction of the "
        "force, W = Fd.",
        f"W = {n(force_w)} × {n(dist_w)} = {n(work)} J.",
        "Part (b). Power is the rate of doing work, P = W / t.",
        f"P = {n(work)} / {n(time_w)} = {n(power)} W.",
    ],
    answer=f"(a) {n(work)} J  (b) {n(power)} W",
))

# ------------------------------------------------------------- 8. energy
mass_ball, height_ball = 0.5, 20.0
pe = mass_ball * G * height_ball
v_ground = (2 * G * height_ball) ** 0.5
EXAMPLES.append(doc(
    num=8, slug="energy-conversion", title="Potential energy converted to kinetic",
    topic="Energy", subtopic="Work, energy and power", section="B1",
    question=(
        f"A ball of mass {n(mass_ball)} kg is held {n(height_ball)} m above the "
        "ground and released. Taking g = 10 m/s² and ignoring air resistance, "
        "find (a) its potential energy before release, (b) its speed as it "
        "reaches the ground."
    ),
    steps=[
        "Part (a). Potential energy is P.E. = mgh.",
        f"P.E. = {n(mass_ball)} × {n(G)} × {n(height_ball)} = {n(pe)} J.",
        "Part (b). All of that becomes kinetic energy at the ground, so "
        "½mv² = mgh. The mass cancels, leaving v = √(2gh).",
        f"v = √(2 × {n(G)} × {n(height_ball)}) = √{n(2*G*height_ball)}.",
        f"v = {n(v_ground)} m/s.",
    ],
    answer=f"(a) {n(pe)} J  (b) {n(v_ground)} m/s",
))

# ------------------------------------------------------------ 9. machines
load, effort, load_dist, effort_dist = 600.0, 200.0, 1.0, 4.0
ma = load / effort
vr = effort_dist / load_dist
efficiency = (ma / vr) * 100
EXAMPLES.append(doc(
    num=9, slug="machine-efficiency", title="Mechanical advantage and efficiency",
    topic="Energy", subtopic="Simple machines", section="B2",
    question=(
        f"An effort of {n(effort)} N raises a load of {n(load)} N. The effort "
        f"moves {n(effort_dist)} m while the load rises {n(load_dist)} m. Find "
        "(a) the mechanical advantage, (b) the velocity ratio, (c) the "
        "efficiency of the machine."
    ),
    steps=[
        "Part (a). Mechanical advantage is load divided by effort, M.A. = L / E.",
        f"M.A. = {n(load)} / {n(effort)} = {n(ma)}.",
        "Part (b). Velocity ratio is the distance moved by the effort divided by "
        "the distance moved by the load.",
        f"V.R. = {n(effort_dist)} / {n(load_dist)} = {n(vr)}.",
        "Part (c). Efficiency = (M.A. / V.R.) × 100%.",
        f"Efficiency = ({n(ma)} / {n(vr)}) × 100 = {n(efficiency)}%.",
        "It is below 100% because some of the effort is spent against friction "
        "and in lifting the moving parts of the machine itself.",
    ],
    answer=f"(a) {n(ma)}  (b) {n(vr)}  (c) {n(efficiency)}%",
))

# ------------------------------------------------------ 10. liquid pressure
density_w, depth = 1000.0, 2.5
pressure = density_w * G * depth
EXAMPLES.append(doc(
    num=10, slug="pressure-in-a-liquid", title="Pressure at a depth in water",
    topic="Matter", subtopic="Pressure", section="C1",
    question=(
        f"Find the pressure due to the water at a depth of {n(depth)} m below the "
        f"surface of a tank. Take the density of water as {n(density_w)} kg/m³ "
        "and g = 10 m/s²."
    ),
    steps=[
        "The pressure due to a column of liquid is P = ρgh, where ρ is the "
        "density and h the depth.",
        f"P = {n(density_w)} × {n(G)} × {n(depth)}.",
        f"P = {n(pressure)} Pa.",
        "This is the pressure due to the water alone. The total pressure at that "
        "depth also includes atmospheric pressure pushing down on the surface.",
    ],
    answer=f"{n(pressure)} Pa ({n(pressure/1000)} kPa)",
))

# ---------------------------------------------------------- 11. upthrust
weight_air, weight_water = 5.0, 3.2
upthrust = weight_air - weight_water
EXAMPLES.append(doc(
    num=11, slug="upthrust", title="Upthrust on a submerged object",
    topic="Matter", subtopic="Pressure", section="C1",
    question=(
        f"A metal block weighs {n(weight_air)} N in air and {n(weight_water)} N "
        "when fully immersed in water. Find (a) the upthrust on the block, "
        "(b) the weight of water it displaces."
    ),
    steps=[
        "Part (a). The apparent loss in weight is the upthrust.",
        f"Upthrust = weight in air − weight in water = {n(weight_air)} − "
        f"{n(weight_water)}.",
        f"Upthrust = {n(upthrust)} N.",
        "Part (b). By Archimedes' principle the upthrust equals the weight of "
        "the fluid displaced.",
        f"So the block displaces {n(upthrust)} N of water.",
    ],
    answer=f"(a) {n(upthrust)} N  (b) {n(upthrust)} N",
))

# ------------------------------------------------------- 12. heat capacity
mass_h, c_water, delta_t = 2.0, 4200.0, 30.0
heat = mass_h * c_water * delta_t
EXAMPLES.append(doc(
    num=12, slug="heat-capacity", title="Heat needed to raise a temperature",
    topic="Matter", subtopic="Heat energy", section="C3",
    question=(
        f"How much heat is needed to raise the temperature of {n(mass_h)} kg of "
        f"water by {n(delta_t)} °C? Take the specific heat capacity of water as "
        f"{n(c_water)} J/kg/K."
    ),
    steps=[
        "The heat needed is Q = mcΔθ, where m is the mass, c the specific heat "
        "capacity and Δθ the temperature rise.",
        f"Q = {n(mass_h)} × {n(c_water)} × {n(delta_t)}.",
        f"Q = {n(heat)} J.",
        f"That is {n(heat/1000)} kJ.",
    ],
    answer=f"{n(heat)} J, or {n(heat/1000)} kJ",
))

# --------------------------------------------------------- 13. latent heat
mass_ice, l_fusion = 0.4, 336000.0
heat_fusion = mass_ice * l_fusion
EXAMPLES.append(doc(
    num=13, slug="latent-heat", title="Heat needed to melt ice",
    topic="Matter", subtopic="Heat energy", section="C3",
    question=(
        f"Find the heat needed to melt {n(mass_ice)} kg of ice at 0 °C into water "
        f"at 0 °C. Take the specific latent heat of fusion of ice as "
        f"{n(l_fusion)} J/kg."
    ),
    steps=[
        "Melting happens at constant temperature, so there is no mcΔθ term. The "
        "heat needed is Q = mL.",
        f"Q = {n(mass_ice)} × {n(l_fusion)}.",
        f"Q = {n(heat_fusion)} J.",
        "The temperature does not change while the ice melts: the energy goes "
        "into breaking the bonds holding the solid together, not into raising "
        "the temperature.",
    ],
    answer=f"{n(heat_fusion)} J, or {n(heat_fusion/1000)} kJ",
))

# ------------------------------------------------------------ 14. gas laws
p1, v1, t1 = 100000.0, 0.02, 300.0
p2, t2 = 150000.0, 360.0
v2 = (p1 * v1 / t1) * (t2 / p2)
EXAMPLES.append(doc(
    num=14, slug="general-gas-law", title="Volume of a gas after a change of state",
    topic="Matter", subtopic="Gas laws", section="C4",
    question=(
        f"A fixed mass of gas occupies {n(v1, 3)} m³ at a pressure of "
        f"{n(p1/1000)} kPa and a temperature of {n(t1)} K. Find its volume when "
        f"the pressure rises to {n(p2/1000)} kPa and the temperature to {n(t2)} K."
    ),
    steps=[
        "For a fixed mass of gas the general gas law applies: P₁V₁ / T₁ = "
        "P₂V₂ / T₂. Temperatures must be in kelvin, and they already are.",
        f"Rearranging for V₂: V₂ = P₁V₁T₂ / (T₁P₂).",
        f"V₂ = ({n(p1/1000)} × {n(v1, 3)} × {n(t2)}) / ({n(t1)} × {n(p2/1000)}).",
        f"V₂ = {n(v2, 4)} m³.",
        "The volume falls because the increase in pressure outweighs the "
        "increase in temperature.",
    ],
    answer=f"{n(v2, 4)} m³",
))

# --------------------------------------------------------------- 15. waves
freq, wavelength = 50.0, 6.0
wave_speed = freq * wavelength
EXAMPLES.append(doc(
    num=15, slug="wave-equation", title="Speed of a wave from frequency and wavelength",
    topic="Waves", subtopic="Wave motion", section="D1",
    question=(
        f"A wave has a frequency of {n(freq)} Hz and a wavelength of "
        f"{n(wavelength)} m. Find (a) its speed, (b) its period."
    ),
    steps=[
        "Part (a). The wave equation is v = fλ.",
        f"v = {n(freq)} × {n(wavelength)} = {n(wave_speed)} m/s.",
        "Part (b). The period is the time for one complete wave, T = 1 / f.",
        f"T = 1 / {n(freq)} = {n(1/freq, 3)} s.",
    ],
    answer=f"(a) {n(wave_speed)} m/s  (b) {n(1/freq, 3)} s",
))

# ---------------------------------------------------------- 16. refraction
n_glass = 1.5
sin_c = 1 / n_glass
EXAMPLES.append(doc(
    num=16, slug="critical-angle", title="Critical angle for glass",
    topic="Waves", subtopic="Refraction of light", section="D2",
    question=(
        f"The refractive index of a glass block is {n(n_glass)}. Find the sine of "
        "the critical angle for light passing from the glass into air, and say "
        "what happens beyond that angle."
    ),
    steps=[
        "At the critical angle the light refracts along the boundary, so the "
        "angle of refraction in air is 90°.",
        "Snell's law gives n = 1 / sin C for light leaving a denser medium into "
        "air, so sin C = 1 / n.",
        f"sin C = 1 / {n(n_glass)} = {n(sin_c, 4)}.",
        "The critical angle is therefore about 42°.",
        "At angles of incidence greater than the critical angle no light escapes: "
        "it is all reflected back into the glass. That is total internal "
        "reflection, and it is what makes an optical fibre work.",
    ],
    answer=f"sin C = {n(sin_c, 4)}, so C ≈ 42°; beyond it, total internal reflection",
))

# -------------------------------------------------------------- 17. lenses
obj_dist, f_lens = 30.0, 10.0
img_dist = 1 / (1 / f_lens - 1 / obj_dist)
magnification = img_dist / obj_dist
EXAMPLES.append(doc(
    num=17, slug="lens-formula", title="Image position and magnification for a lens",
    topic="Waves", subtopic="Lenses", section="D3",
    question=(
        f"An object is placed {n(obj_dist)} cm from a converging lens of focal "
        f"length {n(f_lens)} cm. Find (a) the image distance, (b) the "
        "magnification."
    ),
    steps=[
        "Part (a). The lens formula is 1/f = 1/u + 1/v, so 1/v = 1/f − 1/u.",
        f"1/v = 1/{n(f_lens)} − 1/{n(obj_dist)} = "
        f"{n(1/f_lens, 4)} − {n(1/obj_dist, 4)} = {n(1/f_lens - 1/obj_dist, 4)}.",
        f"v = {n(img_dist)} cm. It is positive, so the image is real and on the "
        "far side of the lens from the object.",
        "Part (b). Magnification m = v / u.",
        f"m = {n(img_dist)} / {n(obj_dist)} = {n(magnification, 3)}.",
        "The magnification is less than 1, so the image is smaller than the "
        "object, and being real it is inverted.",
    ],
    answer=f"(a) {n(img_dist)} cm  (b) {n(magnification, 3)}",
))

# ------------------------------------------------------------ 18. resistors
r1, r2, r3 = 6.0, 3.0, 4.0
r_parallel = 1 / (1 / r1 + 1 / r2)
r_total = r_parallel + r3
EXAMPLES.append(doc(
    num=18, slug="resistors-combined", title="Resistors in parallel and in series",
    topic="Electricity", subtopic="Current electricity", section="E2",
    question=(
        f"A {n(r1)} Ω resistor and a {n(r2)} Ω resistor are connected in "
        f"parallel, and that combination is connected in series with a "
        f"{n(r3)} Ω resistor. Find the total resistance of the circuit."
    ),
    steps=[
        "Take the parallel pair first. For resistors in parallel, "
        "1/R = 1/R₁ + 1/R₂.",
        f"1/R = 1/{n(r1)} + 1/{n(r2)} = {n(1/r1, 4)} + {n(1/r2, 4)} = "
        f"{n(1/r1 + 1/r2, 4)}.",
        f"R = {n(r_parallel)} Ω for the parallel section.",
        "Resistors in series simply add.",
        f"Total = {n(r_parallel)} + {n(r3)} = {n(r_total)} Ω.",
    ],
    answer=f"{n(r_total)} Ω",
))

# -------------------------------------------------------- 19. ohm and power
emf, r_circuit = 12.0, 8.0
current = emf / r_circuit
power_e = emf * current
EXAMPLES.append(doc(
    num=19, slug="ohms-law-power", title="Current and power in a simple circuit",
    topic="Electricity", subtopic="Current electricity", section="E2",
    question=(
        f"A {n(emf)} V battery of negligible internal resistance is connected "
        f"across a {n(r_circuit)} Ω resistor. Find (a) the current, (b) the power "
        "dissipated in the resistor."
    ),
    steps=[
        "Part (a). Ohm's law gives V = IR, so I = V / R.",
        f"I = {n(emf)} / {n(r_circuit)} = {n(current)} A.",
        "Part (b). Power is P = VI.",
        f"P = {n(emf)} × {n(current)} = {n(power_e)} W.",
        f"Checking with P = I²R: {n(current)}² × {n(r_circuit)} = "
        f"{n(current*current*r_circuit)} W, which agrees.",
    ],
    answer=f"(a) {n(current)} A  (b) {n(power_e)} W",
))

# ---------------------------------------------------------- 20. transformer
np_turns, ns_turns, vp = 1000.0, 250.0, 240.0
vs = vp * ns_turns / np_turns
EXAMPLES.append(doc(
    num=20, slug="transformer", title="Output voltage of a transformer",
    topic="Electricity", subtopic="Electromagnetic induction", section="E3",
    question=(
        f"A transformer has {n(np_turns)} turns on its primary coil and "
        f"{n(ns_turns)} turns on its secondary. The primary is connected to a "
        f"{n(vp)} V a.c. supply. Find the secondary voltage, and say what kind of "
        "transformer it is."
    ),
    steps=[
        "For an ideal transformer the turns ratio equals the voltage ratio: "
        "Vs / Vp = Ns / Np.",
        f"Vs = Vp × Ns / Np = {n(vp)} × {n(ns_turns)} / {n(np_turns)}.",
        f"Vs = {n(vs)} V.",
        "The secondary voltage is lower than the primary, so this is a step-down "
        "transformer.",
        "A transformer only works on alternating current: a steady current "
        "produces no changing flux, so no e.m.f. is induced in the secondary.",
    ],
    answer=f"{n(vs)} V, a step-down transformer",
))

# ----------------------------------------------------------- 21. half-life
initial, half_life, elapsed = 800.0, 5.0, 20.0
n_halvings = elapsed / half_life
remaining = initial / (2 ** n_halvings)
EXAMPLES.append(doc(
    num=21, slug="half-life", title="Activity remaining after several half-lives",
    topic="Atomic physics", subtopic="Radioactivity", section="F2",
    question=(
        f"A radioactive sample has a half-life of {n(half_life)} days. If its "
        f"initial count rate is {n(initial)} counts per minute, find the count "
        f"rate after {n(elapsed)} days."
    ),
    steps=[
        "First find how many half-lives have passed.",
        f"Number of half-lives = {n(elapsed)} / {n(half_life)} = "
        f"{n(n_halvings)}.",
        "The count rate halves once per half-life, so divide by 2 that many "
        "times.",
        f"After each: {n(initial)} → {n(initial/2)} → {n(initial/4)} → "
        f"{n(initial/8)} → {n(initial/16)}.",
        f"Count rate = {n(remaining)} counts per minute.",
        "Radioactive decay is random: the half-life is a statistical average, "
        "not a promise about any one nucleus.",
    ],
    answer=f"{n(remaining)} counts per minute",
))


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, text in EXAMPLES:
        (ROOT / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(EXAMPLES)} worked examples to {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
