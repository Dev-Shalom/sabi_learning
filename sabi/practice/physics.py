"""Physics practice templates.

Same discipline as the Mathematics ones: the numbers are sampled, the answer
is computed, and every constant used is stated in the question -- because
that is how the Physics corpus states them, and a practice question that
assumes a value the student has to guess is testing the wrong thing.

g is 10 m/s^2 throughout, matching `corpus/physics`.
"""

from __future__ import annotations

import random
from fractions import Fraction

from sabi.practice.templates import G, Built, n, template


@template(
    "uniform-acceleration-velocity",
    doc="phy-ex-01-uniform-acceleration",
    locator="PEX 1",
    topic="Measurement and mechanics",
    subtopic="Linear motion",
    subject="Physics",
)
def uniform_acceleration_velocity(rng, params=None) -> Built:
    if params is None:
        params = {
            "u": rng.choice([0, 2, 4, 5, 8, 10, 12]),
            "a": rng.choice([2, 3, 4, 5, 6]),
            "t": rng.randint(3, 12),
        }
    u, a, t = params["u"], params["a"], params["t"]

    v = u + a * t
    distance = Fraction(u * t) + Fraction(a * t * t, 2)

    return Built(
        params=params,
        question=(
            f"A body starts with a velocity of {u} m/s and accelerates "
            f"uniformly at {a} m/s^2 for {t} s. Find its final velocity."
        ),
        answer=n(v),
        hint="Give the final velocity in m/s.",
        working=(
            "v = u + at.",
            f"v = {u} + ({a})({t}) = {u} + {a * t}.",
            f"v = {v} m/s. (It covers {n(distance)} m in that time.)",
        ),
    )


@template(
    "free-fall-time",
    doc="phy-ex-02-free-fall",
    locator="PEX 2",
    topic="Measurement and mechanics",
    subtopic="Linear motion",
    subject="Physics",
)
def free_fall_time(rng, params=None) -> Built:
    if params is None:
        # Heights of 5t^2 metres fall for a whole number of seconds, so the
        # answer does not turn on rounding a square root.
        params = {"seconds": rng.randint(2, 6)}
    seconds = params["seconds"]
    height = 5 * seconds * seconds
    speed = G * seconds

    return Built(
        params=params,
        question=(
            f"A stone is dropped from rest from a height of {height} m. How "
            f"long does it take to reach the ground? (Take g = {G} m/s^2.)"
        ),
        answer=n(seconds),
        hint="Give the time in seconds.",
        working=(
            "For a body released from rest, h = (1/2)gt^2.",
            f"{height} = (1/2)({G})t^2 = 5t^2, so t^2 = {seconds * seconds}.",
            f"t = {seconds} s. (It lands at {speed} m/s.)",
        ),
    )


@template(
    "newton-second-law",
    doc="phy-ex-05-newton-second-law",
    locator="PEX 5",
    topic="Measurement and mechanics",
    subtopic="Newton's laws",
    subject="Physics",
)
def newton_second_law(rng, params=None) -> Built:
    if params is None:
        # The acceleration is sampled and the final velocity derived from it,
        # not the other way round. Sampling u, v and t independently makes
        # (v - u)/t a recurring decimal about a third of the time, and "find
        # the force" answered with 52/3 N is not a question anyone sets.
        params = {
            "mass": rng.choice([2, 4, 5, 8, 10, 12, 20]),
            "u": rng.choice([0, 3, 5, 6]),
            "a": rng.choice([2, 3, 4, 5, 6]),
            "t": rng.choice([2, 3, 4, 5, 6]),
        }
    mass, u, a, t = params["mass"], params["u"], params["a"], params["t"]

    v = u + a * t
    acceleration = Fraction(a)
    force = mass * acceleration

    return Built(
        params=params,
        question=(
            f"A force acts on a body of mass {mass} kg, changing its velocity "
            f"from {u} m/s to {v} m/s in {t} s. Find the magnitude of the force."
        ),
        answer=n(force),
        hint="Give the force in newtons.",
        working=(
            f"a = (v - u)/t = ({v} - {u})/{t} = {n(acceleration)} m/s^2.",
            f"F = ma = {mass} x {n(acceleration)}.",
            f"F = {n(force)} N.",
        ),
    )


@template(
    "momentum-collision",
    doc="phy-ex-06-momentum-collision",
    locator="PEX 6",
    topic="Measurement and mechanics",
    subtopic="Momentum",
    subject="Physics",
)
def momentum_collision(rng, params=None) -> Built:
    if params is None:
        # The combined mass is chosen first, from values that divide cleanly,
        # so the common velocity is an exact decimal rather than 15/7.
        total_mass = rng.choice([4, 5, 8, 10, 20])
        m1 = rng.randint(1, total_mass - 1)
        params = {
            "m1": m1,
            "u1": rng.choice([4, 5, 6, 8, 10]),
            "m2": total_mass - m1,
        }
    m1, u1, m2 = params["m1"], params["u1"], params["m2"]

    # The second body is at rest, and the two move off together.
    velocity = Fraction(m1 * u1, m1 + m2)

    return Built(
        params=params,
        question=(
            f"A body of mass {m1} kg moving at {u1} m/s collides with a "
            f"stationary body of mass {m2} kg. If they move off together, find "
            f"their common velocity."
        ),
        answer=n(velocity),
        hint="Give the velocity in m/s.",
        working=(
            "Momentum is conserved: m1u1 + m2u2 = (m1 + m2)v, and u2 = 0.",
            f"({m1})({u1}) = ({m1} + {m2})v, so {m1 * u1} = {m1 + m2}v.",
            f"v = {n(velocity)} m/s.",
        ),
    )


@template(
    "work-and-power",
    doc="phy-ex-07-work-and-power",
    locator="PEX 7",
    topic="Energy",
    subtopic="Work, energy and power",
    subject="Physics",
)
def work_and_power(rng, params=None) -> Built:
    if params is None:
        params = {
            "mass": rng.choice([20, 30, 40, 50, 60, 80]),
            "height": rng.choice([3, 4, 5, 6, 8, 10]),
            "time": rng.choice([2, 4, 5, 8, 10]),
        }
    mass, height, time = params["mass"], params["height"], params["time"]

    work = mass * G * height
    power = Fraction(work, time)

    return Built(
        params=params,
        question=(
            f"A load of mass {mass} kg is raised through a height of {height} m "
            f"in {time} s. Calculate the power developed. (Take g = {G} m/s^2.)"
        ),
        answer=n(power),
        hint="Give the power in watts.",
        working=(
            f"Work done against gravity = mgh = {mass} x {G} x {height} = "
            f"{work} J.",
            f"Power = work / time = {work} / {time}.",
            f"Power = {n(power)} W.",
        ),
    )


@template(
    "machine-efficiency",
    doc="phy-ex-09-machine-efficiency",
    locator="PEX 9",
    topic="Energy",
    subtopic="Simple machines",
    subject="Physics",
)
def machine_efficiency(rng, params=None) -> Built:
    if params is None:
        # Velocity ratio and mechanical advantage are sampled as a pair, with
        # MA < VR always. Sampling load, effort and VR independently produces
        # machines that are more than 100 per cent efficient -- arithmetically
        # consistent, physically impossible, and exactly the kind of wrong
        # thing this product must not hand a student to practise on.
        velocity_ratio, advantage = rng.choice(
            [(2, 1), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4),
             (6, 3), (8, 5), (8, 6), (10, 4), (10, 7), (10, 8)]
        )
        effort = rng.choice([30, 40, 50, 60, 80])
        params = {
            "load": effort * advantage,
            "effort": effort,
            "velocity_ratio": velocity_ratio,
        }
    load, effort = params["load"], params["effort"]
    velocity_ratio = params["velocity_ratio"]

    mechanical_advantage = Fraction(load, effort)
    efficiency = mechanical_advantage / velocity_ratio * 100

    return Built(
        params=params,
        question=(
            f"A machine with a velocity ratio of {velocity_ratio} uses an "
            f"effort of {effort} N to raise a load of {load} N. Find the "
            f"efficiency of the machine."
        ),
        answer=n(efficiency),
        hint="Give the efficiency as a percentage, without the % sign.",
        working=(
            f"Mechanical advantage = load / effort = {load}/{effort} = "
            f"{n(mechanical_advantage)}.",
            f"Efficiency = (MA / VR) x 100 = ({n(mechanical_advantage)} / "
            f"{velocity_ratio}) x 100.",
            f"Efficiency = {n(efficiency)} per cent.",
        ),
    )


@template(
    "pressure-in-a-liquid",
    doc="phy-ex-10-pressure-in-a-liquid",
    locator="PEX 10",
    topic="Matter",
    subtopic="Pressure",
    subject="Physics",
)
def pressure_in_a_liquid(rng, params=None) -> Built:
    if params is None:
        # Depth is stored in centimetres, as a whole number. Everything in
        # `params` is written to JSONB and read back, so a Fraction there
        # would not survive the round trip.
        params = {
            "density": rng.choice([800, 1000, 1200, 1260, 13600]),
            "depth_cm": rng.choice([50, 150, 200, 300, 400, 500, 800]),
        }
    density = params["density"]
    depth = Fraction(params["depth_cm"], 100)

    pressure = density * G * depth

    return Built(
        params=params,
        question=(
            f"Find the pressure at a depth of {n(depth)} m in a liquid of "
            f"density {density} kg/m^3. (Take g = {G} m/s^2.)"
        ),
        answer=n(pressure),
        hint="Give the pressure in pascals.",
        working=(
            "Pressure at a depth in a liquid is P = rho g h.",
            f"P = {density} x {G} x {n(depth)}.",
            f"P = {n(pressure)} Pa.",
        ),
    )


@template(
    "heat-capacity",
    doc="phy-ex-12-heat-capacity",
    locator="PEX 12",
    topic="Matter",
    subtopic="Heat energy",
    subject="Physics",
)
def heat_capacity(rng, params=None) -> Built:
    if params is None:
        params = {
            "mass_grams": rng.choice([200, 250, 400, 500, 800, 1000]),
            "capacity": rng.choice([400, 450, 900, 4200]),
            "rise": rng.choice([10, 15, 20, 25, 30, 40]),
        }
    mass_grams, capacity, rise = (
        params["mass_grams"],
        params["capacity"],
        params["rise"],
    )
    mass = Fraction(mass_grams, 1000)

    heat = mass * capacity * rise

    return Built(
        params=params,
        question=(
            f"Calculate the quantity of heat needed to raise the temperature "
            f"of {mass_grams} g of a substance of specific heat capacity "
            f"{capacity} J/kg/K by {rise} K."
        ),
        answer=n(heat),
        hint="Give the heat energy in joules.",
        working=(
            "Q = mc(change in temperature), with the mass in kilograms.",
            f"m = {mass_grams} g = {n(mass)} kg.",
            f"Q = {n(mass)} x {capacity} x {rise} = {n(heat)} J.",
        ),
    )


@template(
    "wave-equation",
    doc="phy-ex-15-wave-equation",
    locator="PEX 15",
    topic="Waves",
    subtopic="Wave motion",
    subject="Physics",
)
def wave_equation(rng, params=None) -> Built:
    if params is None:
        # Centimetres, for the same JSONB reason as the pressure template.
        params = {
            "frequency": rng.choice([20, 25, 40, 50, 60, 100, 200]),
            "wavelength_cm": rng.choice([25, 50, 150, 200, 300, 400, 500]),
        }
    frequency = params["frequency"]
    wavelength = Fraction(params["wavelength_cm"], 100)

    speed = frequency * wavelength

    return Built(
        params=params,
        question=(
            f"A wave of frequency {frequency} Hz has a wavelength of "
            f"{n(wavelength)} m. Calculate its speed."
        ),
        answer=n(speed),
        hint="Give the speed in m/s.",
        working=(
            "v = f x wavelength.",
            f"v = {frequency} x {n(wavelength)}.",
            f"v = {n(speed)} m/s.",
        ),
    )


@template(
    "resistors-in-parallel",
    doc="phy-ex-18-resistors-combined",
    locator="PEX 18",
    topic="Electricity",
    subtopic="Current electricity",
    subject="Physics",
)
def resistors_in_parallel(rng, params=None) -> Built:
    if params is None:
        # Pairs whose parallel combination is an exact decimal. 3 and 4 ohms
        # give 12/7, which is a fine resistance and a poor practice answer.
        r1, r2 = rng.choice(
            [(2, 2), (2, 3), (2, 6), (2, 8), (3, 6), (3, 12), (4, 4),
             (4, 12), (6, 12), (6, 3), (8, 8), (12, 12), (5, 20), (10, 40)]
        )
        params = {"r1": r1, "r2": r2}
    r1, r2 = params["r1"], params["r2"]

    combined = Fraction(r1 * r2, r1 + r2)

    return Built(
        params=params,
        question=(
            f"Two resistors of {r1} ohms and {r2} ohms are connected in "
            f"parallel. Find their effective resistance."
        ),
        answer=n(combined),
        hint="Give the resistance in ohms.",
        working=(
            "For two resistors in parallel, 1/R = 1/R1 + 1/R2, so "
            "R = R1R2 / (R1 + R2).",
            f"R = ({r1} x {r2}) / ({r1} + {r2}) = {r1 * r2}/{r1 + r2}.",
            f"R = {n(combined)} ohms.",
        ),
    )


@template(
    "ohms-law-power",
    doc="phy-ex-19-ohms-law-power",
    locator="PEX 19",
    topic="Electricity",
    subtopic="Current electricity",
    subject="Physics",
)
def ohms_law_power(rng, params=None) -> Built:
    if params is None:
        # The resistance divides the voltage, so the current is a whole
        # number of amperes and the power is exact.
        voltage, resistance = rng.choice(
            [(6, 2), (6, 3), (12, 4), (12, 6), (24, 8), (24, 12),
             (110, 5), (110, 10), (110, 22), (220, 10), (220, 20),
             (220, 44), (240, 10), (240, 12), (240, 20)]
        )
        params = {"voltage": voltage, "resistance": resistance}
    voltage, resistance = params["voltage"], params["resistance"]

    current = Fraction(voltage, resistance)
    power = voltage * current

    return Built(
        params=params,
        question=(
            f"A potential difference of {voltage} V is applied across a "
            f"resistor of {resistance} ohms. Calculate the power dissipated."
        ),
        answer=n(power),
        hint="Give the power in watts.",
        working=(
            f"From Ohm's law, I = V/R = {voltage}/{resistance} = "
            f"{n(current)} A.",
            f"P = VI = {voltage} x {n(current)}.",
            f"P = {n(power)} W.",
        ),
    )


@template(
    "transformer-turns",
    doc="phy-ex-20-transformer",
    locator="PEX 20",
    topic="Electricity",
    subtopic="Electromagnetic induction",
    subject="Physics",
)
def transformer_turns(rng, params=None) -> Built:
    if params is None:
        # Turns are sampled as a ratio rather than independently, so the
        # secondary voltage is an exact number of volts. 1200:50 on 220 V is
        # a perfectly real transformer and a 36.67 V practice answer.
        primary_turns, secondary_turns = rng.choice(
            [(1000, 100), (1000, 200), (1000, 250), (1000, 500),
             (500, 50), (500, 100), (800, 200), (800, 400),
             (2000, 100), (2000, 500), (400, 800), (400, 2000),
             (500, 1000), (250, 1000)]
        )
        params = {
            "primary_voltage": rng.choice([110, 220, 240]),
            "primary_turns": primary_turns,
            "secondary_turns": secondary_turns,
        }
    primary_voltage = params["primary_voltage"]
    primary_turns = params["primary_turns"]
    secondary_turns = params["secondary_turns"]

    secondary_voltage = Fraction(primary_voltage * secondary_turns, primary_turns)

    return Built(
        params=params,
        question=(
            f"An ideal transformer has {primary_turns} turns in its primary "
            f"coil and {secondary_turns} turns in its secondary coil. If the "
            f"primary is connected to a {primary_voltage} V supply, find the "
            f"secondary voltage."
        ),
        answer=n(secondary_voltage),
        hint="Give the secondary voltage in volts.",
        working=(
            "For an ideal transformer, Vs/Vp = Ns/Np.",
            f"Vs = {primary_voltage} x {secondary_turns}/{primary_turns}.",
            f"Vs = {n(secondary_voltage)} V.",
        ),
    )


@template(
    "half-life-remaining",
    doc="phy-ex-21-half-life",
    locator="PEX 21",
    topic="Atomic physics",
    subtopic="Radioactivity",
    subject="Physics",
)
def half_life_remaining(rng, params=None) -> Built:
    if params is None:
        params = {
            "half_life": rng.choice([2, 4, 5, 6, 10, 20]),
            "halvings": rng.randint(2, 5),
            "initial": rng.choice([64, 80, 96, 128, 160, 256, 320]),
        }
    half_life, halvings = params["half_life"], params["halvings"]
    initial = params["initial"]

    elapsed = half_life * halvings
    remaining = Fraction(initial, 2**halvings)

    return Built(
        params=params,
        question=(
            f"A radioactive sample of mass {initial} g has a half-life of "
            f"{half_life} days. What mass remains after {elapsed} days?"
        ),
        answer=n(remaining),
        hint="Give the remaining mass in grams.",
        working=(
            f"{elapsed} days is {elapsed}/{half_life} = {halvings} half-lives.",
            f"The mass halves {halvings} times: {initial} / 2^{halvings} = "
            f"{initial}/{2 ** halvings}.",
            f"= {n(remaining)} g.",
        ),
    )
