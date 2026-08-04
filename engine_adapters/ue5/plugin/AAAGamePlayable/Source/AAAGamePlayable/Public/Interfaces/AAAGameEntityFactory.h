#pragma once

#include "CoreMinimal.h"
#include "DataTypes/AAAGameRuntimeTypes.h"
#include "UObject/Interface.h"
#include "AAAGameEntityFactory.generated.h"

class AActor;

UINTERFACE(BlueprintType)
class AAAGAMEPLAYABLE_API UAAAGameEntityFactory : public UInterface
{
    GENERATED_BODY()
};

class AAAGAMEPLAYABLE_API IAAAGameEntityFactory
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AAAGame|Runtime")
    AActor* SpawnRuntimeEntity(const FAAAGameEntitySpawnRequest& Request);
};
