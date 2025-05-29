from django.db import models
models.JSONField

class Subject(models.Model):
    title = models.CharField("Название предмета", max_length=64, unique=True)
    def __str__(self):
        return self.title

class TgUser(models.Model):
    EXAM_CHOICES = (("OGE", "ОГЭ"), ("EGE", "ЕГЭ"))
    LEVEL_CHOICES = (("basic", "базовый"), ("middle", "средний"), ("high", "высокий"))

    tg_id = models.BigIntegerField("ID в Telegram", unique=True)
    name = models.CharField("Имя", max_length=128)
    is_registered = models.BooleanField("Зарегистрирован", default=False)
    exam_type = models.CharField("Экзамен", max_length=3, choices=EXAM_CHOICES, blank=True)
    class_level = models.CharField("Класс", max_length=10, blank=True)
    subject_goals = models.JSONField("Желаемые баллы по предметам", blank=True, default=dict)
    trial_scores = models.JSONField("Пробные баллы по предметам", blank=True, default=dict)
    days_left = models.CharField("Дней до экзамена", max_length=16, blank=True, null=True)
    subjects = models.ManyToManyField(Subject, verbose_name="Предметы", blank=True)
    daily_level = models.CharField("Уровень ежедневных задач", max_length=8, choices=LEVEL_CHOICES, default="basic")
    notify_time = models.TimeField("Время уведомлений", default="19:00", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.tg_id})"

class Task(models.Model):
    EXAM_CHOICES = (("OGE", "ОГЭ"), ("EGE", "ЕГЭ"))
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Предмет")
    exam_type = models.CharField("Экзамен", max_length=3, choices=EXAM_CHOICES)
    number = models.CharField("Номер задания", max_length=8)
    subtype = models.CharField("Тип задачи", max_length=32, blank=True)
    title = models.CharField("Название", max_length=128, blank=True)
    theory_file = models.FileField("Файл теории", upload_to="theory/", blank=True)
    train_file1 = models.FileField("Тренажёр 1", upload_to="trainers/", blank=True)
    train_file2 = models.FileField("Тренажёр 2", upload_to="trainers/", blank=True)
    answer_file = models.FileField("Ответы", upload_to="answers/", blank=True)
    video_link = models.URLField("Видео-теория", blank=True)
    video_practice = models.URLField("Видео-практика", blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        unique_together = ("subject", "exam_type", "number", "subtype")

    def __str__(self):
        if self.subtype:
            return f"{self.subject} [{self.get_exam_type_display()}] №{self.number} ({self.subtype})"
        return f"{self.subject} [{self.get_exam_type_display()}] №{self.number}"

# models.py

class PlanText(models.Model):
    EXAM_CHOICES = (("OGE", "ОГЭ"), ("EGE", "ЕГЭ"))

    exam_type = models.CharField("Экзамен", max_length=3, choices=EXAM_CHOICES)
    subject = models.CharField("Предмет", max_length=64)
    desired_score = models.CharField("Желаемая оценка/балл", max_length=16)
    trial_score = models.CharField("Баллы на пробнике", max_length=32)
    text = models.TextField("Текст плана")

    class Meta:
        unique_together = ("exam_type", "subject", "desired_score", "trial_score")
        verbose_name = "План подготовки"
        verbose_name_plural = "Планы подготовки"

    def __str__(self):
        return f"{self.get_exam_type_display()} | {self.subject} | {self.desired_score} | {self.trial_score}"

class DailyQuestion(models.Model):
    LEVEL_CHOICES = (("basic", "базовый"), ("middle", "средний"), ("high", "высокий"))
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Предмет")
    level = models.CharField("Уровень", max_length=8, choices=LEVEL_CHOICES)
    text = models.TextField("Вопрос")
    answer = models.TextField("Ответ")
    explanation = models.TextField("Пояснение", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    sent_count = models.PositiveIntegerField("Отправлен", default=0)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    def __str__(self):
        return f"Q{self.pk} {self.subject} {self.level}"

class Broadcast(models.Model):
    STATUS_CHOICES = (
        ("pending", "Запланировано"),
        ("sent", "Отправлено"),
        ("failed", "Ошибка"),
    )
    text = models.TextField("Текст сообщения")
    file = models.FileField("Вложение", upload_to="broadcasts/", blank=True)
    target_filter = models.JSONField("Фильтр аудитории")
    send_at = models.DateTimeField("Время отправки")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    def __str__(self):
        return f"Broadcast {self.id} [{self.status}]"
