import ingenialink as il


class Capture:
    """Capture.
    """

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def create_poller(self, registers, servo="default", sampling_time=0.125, buffer_size=100, start=True):
        """
        Returns a Poller instance with target registers.

        Args:
            registers (list of dict): list of registers to add to the Poller. Dicts should have the follow format:

                .. code-block:: python

                    [
                        { # Poller register one
                            "name": "CL_POS_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis. If it has no axis field, by default axis 1.
                        },
                        { # Poller register two
                            "name": "CL_VEL_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis. If it has no axis field, by default axis 1.
                        }
                    ]

            servo (str): servo alias to reference it. ``default`` by default.
            sampling_time (float): period of the sampling in seconds. By default ``0.125`` seconds.
            buffer_size (int): number maximum of sample for each data read. ``100`` by default.
            start (bool): if ``True``, function starts poller, if ``False`` poller should be started after.
             ``True`` by default.

        Returns:
            Poller: Poller object with chosen registers.

            Poller.start()
                Poller starts reading the registers.

            Poller.stop()
                Poller stop reading the registers.

            Poller.data
                tuple with 3 items: a list of timestamp, list of lists of values (one list of values for each register),
                and a boolean that indicates if data was lost.

                When the poller starts, the lists are filled with the timestamp and the value of the registers reading.
                The maximum length of the list will be buffer_size value, when this size is reached,
                the older value will be removed and the newest will be added.

                When the property data is read list are reset to a empty list.
        """
        drive = self.mc.servos[servo]
        if self.mc.net[servo].prot == il.NET_PROT.CAN:
            poller = il.CANOpenPoller(self.mc.servos[servo], len(registers))
        else:
            poller = il.Poller(self.mc.servos[servo], len(registers))
        poller.configure(sampling_time, buffer_size)
        for index, register in enumerate(registers):
            axis = register.get("axis", 1)
            name = register.get("name")
            register_obj = drive.dict.get_regs(axis)[name]
            poller.ch_configure(index, register_obj)
        if start:
            poller.start()
        return poller
