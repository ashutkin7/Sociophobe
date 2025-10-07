from rest_framework import permissions

class IsSurveyParticipantOrAdmin(permissions.BasePermission):
    """
    Разрешает доступ:
    - респонденту, если он участвовал в опросе;
    - модератору или заказчику, если они создатели опроса.
    """

    def has_permission(self, request, view):
        user = request.user
        print(f"[PERM DEBUG] Проверка пользователя={user}, роль={getattr(user, 'role', None)}, аутентифицирован={user.is_authenticated}")
        return bool(user and user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = getattr(user, 'role', None)
        print(f"[PERM DEBUG] has_object_permission для {user} (роль={role}) и опроса ID={obj.survey_id}")

        if role in ["moderator", "customer"] and obj.creator == user:
            print("[PERM DEBUG] ✅ Администратор/модератор имеет доступ.")
            return True

        if role == "respondent":
            from surveys.models import RespondentAnswers
            has_answers = RespondentAnswers.objects.filter(
                respondent=user,
                survey_question__survey=obj
            ).exists()
            print(f"[PERM DEBUG] Проверка ответов респондента → {has_answers}")
            return has_answers

        print("[PERM DEBUG] ❌ Доступ запрещён.")
        return False
