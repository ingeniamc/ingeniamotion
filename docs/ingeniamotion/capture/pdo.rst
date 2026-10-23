PDO
===

Selecting PDO Participants
--------------------------

On EtherCAT, PDO exchange is managed per network. The ``servo`` argument selects the network;
the optional ``servos`` argument selects which servo aliases participate in the exchange. Every
alias in ``servos`` must be connected and discovered on that network. If ``servos`` is omitted,
all mapped servos on the selected network participate.

Configure the PDO maps before starting the exchange. For example, to exchange process data only
with two servos on the same network:

.. code-block:: python

   mc.capture.pdo.start_pdos(
       refresh_rate=0.01,
       servo="servo_1",
       servos={"servo_1", "servo_2"},
   )

Only one PDO configuration can be active per network. Stop the existing exchange before changing
the selected participants or timing. ``stop_pdos`` stops the exchange for the entire network, even
when it was started with a subset of that network's servos:

.. code-block:: python

   mc.capture.pdo.stop_pdos(servo="servo_1")

API Reference
-------------

.. automodule:: ingeniamotion.pdo
   :members:
