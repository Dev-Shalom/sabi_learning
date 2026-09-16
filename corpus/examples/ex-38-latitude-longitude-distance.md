---
doc_id: ex-38-latitude-longitude-distance
title: Distance along a parallel of latitude
source: Sabi worked example, WAEC Paper 2 style
attribution: worked_example
topic: Mensuration
subtopic: Longitude and latitude
syllabus_section: C3
locator: EX 38
---

## Question

Two towns P and Q both lie on latitude 60 degrees north. P is on longitude 15
degrees east and Q is on longitude 45 degrees east. Taking the radius of the earth
as 6400 km and pi as 22/7, find the distance between them along their common
parallel of latitude, correct to the nearest kilometre.

## Solution

1. Both places are east of Greenwich, so subtract the longitudes:
   difference = 45 - 15 = 30 degrees.
2. Distance along a parallel of latitude theta is
   (longitude difference over 360) times 2 pi R cos theta.
3. cos 60 degrees = 0.5.
4. 2 pi R = 2 times (22/7) times 6400 = 281600/7, which is about 40228.57 km.
5. Multiply by cos 60: 40228.57 times 0.5 = 20114.29 km.
6. Multiply by 30/360, that is divide by 12: 20114.29 divided by 12 = 1676.19 km.

**Answer: about 1676 km.**

## Common mistake

Leaving out the cos theta factor. That factor is what makes a parallel of latitude
a small circle rather than a great circle; without it you would be computing a
distance along the equator.
