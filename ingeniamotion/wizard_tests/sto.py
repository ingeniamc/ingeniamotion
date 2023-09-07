import ingenialogger

from enum import IntEnum

from .base_test import BaseTest
from ingeniamotion.enums import SeverityLevel
from .. import MotionController


class STOTest(BaseTest):
    """STO test."""

    class ResultType(IntEnum):
        STO_INACTIVE = 0
        STO_ACTIVE = -1
        STO_ABNORMAL_LATCHED = -2
        STO_ABNORMAL = -3
        STO_ABNORMAL_SUPPLY = -4
        STO_INPUTS_DIFFER = -5

    class Polarity(IntEnum):
        NORMAL = 0
        REVERSED = 1

    result_description = {
        ResultType.STO_INACTIVE: "STO Inactive",
        ResultType.STO_ACTIVE: "STO Active",
        ResultType.STO_ABNORMAL_LATCHED: "Abnormal STO Latched",
        ResultType.STO_ABNORMAL: "Abnormal STO",
        ResultType.STO_ABNORMAL_SUPPLY: "Abnormal Supply",
        ResultType.STO_INPUTS_DIFFER: "STO Inputs Differ",
    }

    STO_STATUS_REGISTER = "DRV_PROT_STO_STATUS"

    STO1_ACTIVE_BIT = 0x1
    STO2_ACTIVE_BIT = 0x2
    STO_SUPPLY_FAULT_BIT = 0x4
    STO_ABNORMAL_FAULT_BIT = 0x8
    STO_REPORT_BIT = 0x10

    BACKUP_REGISTERS: list[str] = []

    def __init__(self, mc: MotionController, servo: str, axis: int) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.suggested_registers = {}

    def setup(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def loop(self) -> ResultType:
        if self.mc.configuration.is_sto1_active(servo=self.servo, axis=self.axis) == 0:
            self.logger.info("STO1 bit is LOW")
        # Check STO1 status --> Check bit 0 (0x1 in HEX)
        else:
            self.logger.info("STO1 bit is HIGH")

        if self.mc.configuration.is_sto2_active(servo=self.servo, axis=self.axis) == 0:
            self.logger.info("STO2 bit is LOW")
        # Check STO2 status --> Check bit 1 (0x2 in HEX)
        else:
            self.logger.info("STO2 bit is HIGH")

        # Check STO supply fault status --> Check bit 2 (0x4 in HEX)
        sto_power_supply = self.mc.configuration.check_sto_power_supply(
            servo=self.servo, axis=self.axis
        )
        if sto_power_supply == 0:
            self.logger.info("STO Power Supply is LOW")
        else:
            self.logger.info("STO Power Supply is HIGH")

        # Check STO abnormal fault status --> Check bit 3 (0x8 in HEX)
        sto_abnormal_fault = self.mc.configuration.check_sto_abnormal_fault(
            servo=self.servo, axis=self.axis
        )
        if sto_abnormal_fault == 0:
            self.logger.info("STO abnormal fault bit is LOW")
        else:
            self.logger.info("STO abnormal fault bit is HIGH")

        # Check STO report --> Check bit 4 (0x10 in HEX)
        if self.mc.configuration.get_sto_report_bit(servo=self.servo, axis=self.axis) == 0:
            self.logger.info("STO report is LOW")
        else:
            self.logger.info("STO report is HIGH")

        # Check STO STATE
        if self.mc.configuration.is_sto_active(servo=self.servo, axis=self.axis):
            return self.ResultType.STO_ACTIVE
        elif self.mc.configuration.is_sto_inactive(servo=self.servo, axis=self.axis):
            return self.ResultType.STO_INACTIVE
        elif self.mc.configuration.is_sto_abnormal_latched(servo=self.servo, axis=self.axis):
            return self.ResultType.STO_ABNORMAL_LATCHED
        elif sto_abnormal_fault != 0:
            return self.ResultType.STO_ABNORMAL
        elif sto_power_supply == 0:
            return self.ResultType.STO_ABNORMAL_SUPPLY
        else:
            return self.ResultType.STO_INPUTS_DIFFER

    def get_result_msg(self, output: ResultType) -> str:
        return self.result_description[output]

    def get_result_severity(self, output: ResultType) -> SeverityLevel:
        if output < self.ResultType.STO_INACTIVE:
            return SeverityLevel.FAIL
        else:
            return SeverityLevel.SUCCESS
