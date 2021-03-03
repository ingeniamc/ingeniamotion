What is Ingeniamotion?
======================

Ingeniamotion is a library over ingenialink to work simply and easily with Ingenia's drives.

How it works?
-------------

All ingeniamotion functionalities works through class MotionController. So, first of all we should
instantiate a MotionController object.

.. code-block:: python

    from ingeniamotion import MotionController
    mc = MotionController()

Now, ``mc`` is our MotionController instance.

Then, we should connect some servos.

.. code-block:: python

    # If we will connect only one servo
    mc.communication.connect_servo_eoe("192.168.2.22", "eve-net_1.7.0.xdf")

    # If we will connect more servos
    mc.communication.connect_servo_eoe("192.168.2.22", "eve-net_1.7.0.xdf",
                                       alias="servo_one")
    mc.communication.connect_servo_eoe("192.168.2.23", "eve-net_1.7.0.xdf",
                                       alias="servo_two")
    # "alias" field will allow reference these servos in the future.
    # "alias" can be what we want.

Now, the servos are ready and we can work with they.

We can apply some configurations:

.. code-block:: python

    # If we have only one servo
    mc.configuration.release_brake()
    # By default it use the axis 1

Or we can execute some tests or calibrations:

.. code-block:: python

    mc.tests.digital_halls_test(servo="servo_one", subnode=1)

    mc.tests.commutation(servo="servo_two", subnode=1)

MotionController namespaces
---------------------------

MotionController functionalities are group in different namespaces.

**Motion**

In this namespace we will found all the functions that will help us to move the servos.

**Communication**

This namespace has all the functions to make simple communication with the servo:
connect, read or write a register, load or save configuration, load firmware, etc.

**Configuration**

Here we will found functions to configure the servo: configure limits, feedbacks, brake settings, etc.

**Capture**

This namespace will help us of work with monitoring and similar.

**Tests**

The functions of this namespace will help us to lunch some test for the commissioning process.
