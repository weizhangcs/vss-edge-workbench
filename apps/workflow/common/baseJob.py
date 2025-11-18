# 文件路径: apps/workflow/common/base_job.py

from model_utils.models import TimeStampedModel
from model_utils import Choices
from django_fsm import FSMField, transition


class BaseJob(TimeStampedModel):
    """
    所有原子任务的抽象基类。
    """
    STATUS = Choices(('PENDING', '待处理'), ('QUEUED', '排队中'), ('PROCESSING', '处理中'), ('COMPLETED', '已完成'),
                     ('REVISING', '修订中'), ('ERROR', '错误'), ('QA_PENDING', '待审核'))

    status = FSMField(
        default=STATUS.PENDING,
        choices=STATUS,
        protected=True,
        verbose_name="任务状态"
    )

    @transition(field='status', source='*', target=STATUS.PROCESSING)
    def start(self): pass

    # [FIX 2a] 允许从 'QA_PENDING' 状态转换到 'COMPLETED'
    @transition(field='status', source=[STATUS.PROCESSING, STATUS.REVISING, STATUS.QA_PENDING], target=STATUS.COMPLETED)
    def complete(self): pass

    # [FIX 2b] 添加一个新的转换方法，用于从 'PROCESSING' 到 'QA_PENDING'
    @transition(field='status', source=STATUS.PROCESSING, target=STATUS.QA_PENDING)
    def queue_for_qa(self):
        """(新) 标记为已处理，等待下一步（例如分发）。"""
        pass

    @transition(field='status', source=STATUS.COMPLETED, target=STATUS.REVISING)
    def revise(self):
        """
        定义一个从“已完成”到“修订中”的状态转换。
        具体的实现逻辑由子类负责。
        """
        pass

    @transition(field='status', source='*', target=STATUS.ERROR)
    def fail(self): pass

    class Meta:
        abstract = True