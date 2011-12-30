/*
    Copyright (c) Mathias Kaerlev 2011.

    This file is part of pyspades.

    pyspades is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    pyspades is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with pyspades.  If not, see <http://www.gnu.org/licenses/>.

*/

/*
world_c.cpp - this shit is hazardous
*/

// Cython->C++

#define isvoxelsolidwrap __pyx_f_8pyspades_5world_isvoxelsolidwrap

static int isvoxelsolidwrap(void *, float, float, float);

#include <math.h>

struct Vector3
{
    float x, y, z;
};

struct LongVector3
{
    long x, y, z;
};

struct Orientation
{
    Vector3 f, s, h;
};

inline void get_orientation(Orientation * o,
                            float orientation_x, 
                            float orientation_y,
                            float orientation_z)
{
    float f;
    o->f.x = orientation_x;
    o->f.y = orientation_y;
    o->f.z = orientation_z;
    f = sqrtf(orientation_x*orientation_x + orientation_y*orientation_y);
    o->s.x = -orientation_y/f;
    o->s.y = orientation_x/f;
    o->s.z = 0.0f;
    o->h.x = -orientation_z*o->s.y;
    o->h.y = orientation_z*o->s.x;
    o->h.z = orientation_x*o->s.y - orientation_y*o->s.x;
}

float distance3d(float x1, float y1, float z1, float x2, float y2, float z2)
{
    return sqrtf(pow(x2-x1, 2) + pow(y2-y1,2) + pow(z2-z1,2));
}

int validate_hit(float shooter_x, float shooter_y, float shooter_z,
                 float orientation_x, float orientation_y, float orientation_z, 
                 float ox, float oy, float oz, 
                 float tolerance)
{
    float cx, cy, cz, r, x, y;
    Orientation o;
    get_orientation(&o, orientation_x, orientation_y, orientation_z);
    ox -= shooter_x;
    oy -= shooter_y;
    oz -= shooter_z;
    cz = ox * o.f.x + oy * o.f.y + oz * o.f.z;
    r = 1.f/cz;
    cx = ox * o.s.x + oy * o.s.y + oz * o.s.z;
    x = cx * r;
    cy = ox * o.h.x + oy * o.h.y + oz * o.h.z;
    y = cy * r;
    r *= tolerance;
    return (x-r < 0 && x+r > 0 && y-r < 0 && y+r > 0);
}

// silly VOXLAP function
inline void ftol(float f, long *a)
{
    *a = (long)f;
}

long can_see(void * map, float x0, float y0, float z0, float x1, float y1,
             float z1)
{
    Vector3 f, g;
    LongVector3 a, c, d, p, i;
    long cnt = 0;

    ftol(x0-.5f,&a.x); ftol(y0-.5f,&a.y); ftol(z0-.5f,&a.z);
    ftol(x1-.5f,&c.x); ftol(y1-.5f,&c.y); ftol(z1-.5f,&c.z);

    if (c.x <  a.x) {
        d.x = -1; f.x = x0-a.x; g.x = (x0-x1)*1024; cnt += a.x-c.x;
    }
    else if (c.x != a.x) {
        d.x =  1; f.x = a.x+1-x0; g.x = (x1-x0)*1024; cnt += c.x-a.x;
    }
    else 
        f.x = g.x = 0;
    if (c.y <  a.y) {
        d.y = -1; f.y = y0-a.y;   g.y = (y0-y1)*1024; cnt += a.y-c.y;
    }
    else if (c.y != a.y) {
        d.y =  1; f.y = a.y+1-y0; g.y = (y1-y0)*1024; cnt += c.y-a.y;
    }
    else
        f.y = g.y = 0;
    if (c.z <  a.z) {
        d.z = -1; f.z = z0-a.z;   g.z = (z0-z1)*1024; cnt += a.z-c.z;
    }
    else if (c.z != a.z) {
        d.z =  1; f.z = a.z+1-z0; g.z = (z1-z0)*1024; cnt += c.z-a.z;
    }
    else
        f.z = g.z = 0;

    ftol(f.x*g.z - f.z*g.x,&p.x); ftol(g.x,&i.x);
    ftol(f.y*g.z - f.z*g.y,&p.y); ftol(g.y,&i.y);
    ftol(f.y*g.x - f.x*g.y,&p.z); ftol(g.z,&i.z);

    if (cnt > 32)
        cnt = 32;
    while (cnt)
    {
        if (((p.x|p.y) >= 0) && (a.z != c.z)) {
            a.z += d.z; p.x -= i.x; p.y -= i.y;
        }
        else if ((p.z >= 0) && (a.x != c.x)) {
            a.x += d.x; p.x += i.z; p.z -= i.y;
        }
        else {
            a.y += d.y; p.y += i.z; p.z += i.x;
        }

        if (isvoxelsolidwrap(map, a.x, a.y,a.z))
            return 0;
        cnt--;
    }
    return 1;
}