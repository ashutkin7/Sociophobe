from rest_framework import serializers
from .models import Users, Characteristics, CharacteristicValues, RespondentCharacteristics


class UserMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = ['user_id', 'name', 'email', 'role']


class UserStatsSerializer(serializers.Serializer):
    completed_surveys = serializers.IntegerField()
    earned_money = serializers.DecimalField(max_digits=10, decimal_places=2)


# ---------- ХАРАКТЕРИСТИКИ ----------
class CharacteristicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Characteristics
        fields = ['characteristic_id', 'name', 'value_type', 'requirements']

    def validate(self, data):
        value_type = data.get("value_type")
        requirements = (data.get("requirements") or "").strip()

        # === Проверка типов ===
        if value_type not in ["numeric", "string", "choice"]:
            raise serializers.ValidationError("value_type должен быть 'numeric', 'string' или 'choice'.")

        # === Валидация numeric ===
        if value_type == "numeric":
            try:
                parts = [int(x.strip()) for x in requirements.split(",")]
                if len(parts) != 2 or parts[0] >= parts[1]:
                    raise ValueError
            except Exception:
                raise serializers.ValidationError(
                    "Для числового типа требования должны быть в формате 'min,max' (например '18,65')."
                )

        # === Валидация choice ===
        elif value_type == "choice":
            if not requirements or ";" not in requirements:
                raise serializers.ValidationError(
                    "Для типа 'choice' перечислите варианты через ';' (например 'м;ж')."
                )

        # === string не требует ограничений ===
        elif value_type == "string" and requirements:
            raise serializers.ValidationError("Для типа 'string' поле 'requirements' должно быть пустым.")

        return data


class RespondentCharacteristicSerializer(serializers.ModelSerializer):
    characteristic_id = serializers.IntegerField(source='characteristic_value.characteristic.characteristic_id', read_only=True)
    characteristic_name = serializers.CharField(source='characteristic_value.characteristic.name', read_only=True)
    value = serializers.CharField(source='characteristic_value.value_text')

    class Meta:
        model = RespondentCharacteristics
        fields = ['characteristic_id', 'characteristic_name', 'value']

    def create_or_update(self, user, data):
        for item in data:
            char_id = item['characteristic_id']
            value_text = item['value']
            characteristic = Characteristics.objects.get(characteristic_id=char_id)

            # 🔍 Проверка по типу
            if characteristic.value_type == "numeric":
                try:
                    num_value = float(value_text)
                    limits = [float(x.strip()) for x in characteristic.requirements.split(",")]
                    if not (limits[0] <= num_value <= limits[1]):
                        raise serializers.ValidationError(
                            f"Значение '{value_text}' не входит в диапазон {limits[0]}–{limits[1]}"
                        )
                except ValueError:
                    raise serializers.ValidationError(f"Поле '{characteristic.name}' должно быть числом.")

            elif characteristic.value_type == "choice":
                allowed = [v.strip() for v in characteristic.requirements.split(";")]
                if value_text not in allowed:
                    raise serializers.ValidationError(
                        f"Недопустимое значение '{value_text}'. Разрешено: {', '.join(allowed)}"
                    )

            # Строковый тип — без ограничений
            value_obj, _ = CharacteristicValues.objects.get_or_create(
                characteristic=characteristic,
                value_text=value_text
            )
            RespondentCharacteristics.objects.update_or_create(
                user=user, characteristic_value=value_obj
            )
        return RespondentCharacteristics.objects.filter(user=user)
