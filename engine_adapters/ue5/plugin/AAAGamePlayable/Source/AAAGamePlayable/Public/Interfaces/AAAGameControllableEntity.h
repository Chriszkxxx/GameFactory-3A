#pragma once

#include "CoreMinimal.h"
#include "DataTypes/AAAGameRuntimeTypes.h"
#include "UObject/Interface.h"
#include "AAAGameControllableEntity.generated.h"

UINTERFACE(BlueprintType)
class AAAGAMEPLAYABLE_API UAAAGameControllableEntity : public UInterface
{
    GENERATED_BODY()
};

class AAAGAMEPLAYABLE_API IAAAGameControllableEntity
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AAAGame|Runtime")
    FString GetRuntimeEntityId() const;

    UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AAAGame|Runtime")
    void SetRuntimeEntityId(const FString& EntityId);

    UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AAAGame|Runtime")
    bool ApplyRuntimeInput(const FAAAGameRuntimeInputState& InputState);

    UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AAAGame|Runtime")
    FAAAGameEntitySnapshot GetRuntimeSnapshot() const;
};
