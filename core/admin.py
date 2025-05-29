from django.contrib import admin
from .models import Subject, TgUser, Task, DailyQuestion, Broadcast, PlanText

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("id", "title")
    search_fields = ("title",)

@admin.register(TgUser)
class TgUserAdmin(admin.ModelAdmin):
    list_display = (
        "tg_id", "name", "is_registered", "exam_type", "class_level",
        "daily_level", "notify_time", "created_at", "display_subject_goals"
    )
    list_filter = ("is_registered", "exam_type", "class_level", "daily_level")
    search_fields = ("name", "tg_id")
    filter_horizontal = ("subjects",)
    def display_subject_goals(self, obj):
        goals = obj.subject_goals
        if not isinstance(goals, dict) or not goals:
            return "-"
        from .models import Subject
        subjects = Subject.objects.in_bulk(goals.keys())
        return ", ".join([
            f"{subjects.get(int(sub_id)).title if subjects.get(int(sub_id)) else sub_id}: {goal}"
            for sub_id, goal in goals.items()
        ])
    display_subject_goals.short_description = "Желаемые баллы"

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id", "subject", "exam_type", "number", "subtype", "title",
        "theory_file", "train_file1", "train_file2",
        "answer_file", "video_link", "video_practice", "updated_at"
    )
    list_filter = ("subject", "exam_type", "subtype")
    search_fields = ("subject__title", "number", "title", "subtype")
    autocomplete_fields = ("subject",)


@admin.register(PlanText)
class PlanTextAdmin(admin.ModelAdmin):
    list_display = ("exam_type", "subject", "desired_score", "trial_score", "short_text")
    search_fields = ("subject", "text")
    list_filter = ("exam_type", "subject", "desired_score", "trial_score")
    def short_text(self, obj):
        return obj.text[:30] + "..." if len(obj.text) > 30 else obj.text
    short_text.short_description = "Текст"


@admin.register(DailyQuestion)
class DailyQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "level", "text", "is_active", "sent_count", "created_at")
    list_filter = ("subject", "level", "is_active")
    search_fields = ("text",)
    autocomplete_fields = ("subject",)

@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "send_at", "file", "created_at")
    list_filter = ("status",)
    search_fields = ("text",)
    readonly_fields = ("status", "created_at")
