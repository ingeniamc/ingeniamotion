from summit_testing_framework.configuration.feedback_constants import FeedbackSensorType
from summit_testing_framework.setups.specifiers import PartNumber

AVAILABLE_FEEDBACKS_BY_PART_NUMBER = {
    PartNumber.EVE_XCR_C: (FeedbackSensorType.QEI, FeedbackSensorType.HALLS),
    PartNumber.EVE_XCR_E: (FeedbackSensorType.QEI, FeedbackSensorType.HALLS),
    PartNumber.CAP_XCR_C: (FeedbackSensorType.ABS1,),
    PartNumber.CAP_XCR_E: (FeedbackSensorType.ABS1,),
    PartNumber.EVS_NET_E: (
        FeedbackSensorType.ABS1,
        FeedbackSensorType.QEI,
        FeedbackSensorType.HALLS,
    ),
}
