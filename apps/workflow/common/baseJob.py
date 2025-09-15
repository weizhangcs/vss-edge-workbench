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

    @transition(field='status', source=['PROCESSING', 'REVISING'], target=STATUS.COMPLETED)
    def complete(self): pass

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