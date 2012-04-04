#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from matplotlib import rc
rc('text', usetex=True)
rc('font', family='serif')



def plot_interval(a,c,x_left, x_right,i, fbound):
    lh = c*(1-a[0])
    rh = c*(1+a[1])
    x=arange(x_left, x_right+1)
    y=0*x
    arrow_r = Arrow(c,0, c*a[1],0,0.2)
    arrow_l = Arrow(c,0,-c*a[0],0,0.2)
    plot(x,y)
    text((x_left+lh)/2.0,0.1,'freebound interval [%s, %s] is penalty-free' % (lh,rh))
    text((x_left+lh)/2.0, 0.2, 'rhs=%s,    %s' % (c, fbound))
    cur_ax = gca()
    cur_ax.add_patch(arrow_l)
    cur_ax.add_patch(arrow_r)
    axis([x_left,x_right,-0.1,0.3])
    yticks([])
    title('Elasticized constraint\_%s   $C(x)= %s $' % (i, c))

figure()
subplots_adjust(hspace=0.5)

fbound = 'proportionFreeBound'
i=1
subplot(2,1,i)
a=[0.01,0.01]
c = 200
x_left = 0.97*c
x_right = 1.03*c
fb_string = '%s%s = %s' %(fbound,'', a[0])
plot_interval(a,c,x_left, x_right,i, fb_string)

i += 1
subplot(2,1,i)
a=[0.02, 0.05]
c = 500
x_left = 0.9*c  #scale of window
x_right = 1.2*c #scale of window
fb_string = '%s%s = [%s,%s]' % (fbound,'List', a[0],a[1])
plot_interval(a,c,x_left, x_right,i, fb_string)
savefig('freebound.jpg')
savefig('freebound.pdf')

# vim: fenc=utf-8: ft=python:sw=4:et:nu:fdm=indent:fdn=1:syn=python

